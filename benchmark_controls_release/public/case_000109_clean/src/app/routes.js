const fs = require('fs');
const path = require('path');
const marked = require('marked');

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

function sanitizeMarkdown(content) {
  // Strip raw HTML from the markdown source before rendering. `marked` is a
  // renderer, not an HTML sanitizer, and allows embedded HTML by default,
  // which would otherwise produce stored XSS when the preview is rendered.
  // We pre-escape `<` and `>` so any inline HTML becomes inert text; pure
  // markdown syntax (backticks, asterisks, links, headings) is unaffected.
  const escaped = String(content).replace(/[<>]/g, ch => (ch === '<' ? '&lt;' : '&gt;'));
  return marked(escaped, { breaks: true, gfm: true });
}

function safeJsonForScript(value) {
  return JSON.stringify(value).replace(/[<>&\u2028\u2029]/g, ch => ({
    '<': '\\u003c',
    '>': '\\u003e',
    '&': '\\u0026',
    '\u2028': '\\u2028',
    '\u2029': '\\u2029'
  }[ch]));
}

// Legacy: Reflects 'uri' parameter in HTML response body for v1 file tracking system
function handleFileUpload(req, res, db) {
  const uri = req.body?.uri || '';
  const filename = req.file?.originalname || 'unknown';

  if (!req.session.user_id) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // Save file metadata to database
  const now = new Date().toISOString();
  try {
    db.prepare('INSERT INTO files (user_id, filename, path, created_at) VALUES (?, ?, ?, ?)')
      .run(req.session.user_id, filename, uri, now);
  } catch (err) {
    console.error('Error recording file metadata:', err.message);
  }

  const safeUri = escapeHtml(String(uri));
  const safeFilename = escapeHtml(String(filename));

  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.send(`<!DOCTYPE html>
<html>
<head><title>Upload Complete</title></head>
<body>
<h2>File Upload Successful</h2>
<p>Your file has been processed.</p>
<p><strong>Destination Path:</strong> ${safeUri}</p>
<p><strong>Original Filename:</strong> ${safeFilename}</p>
<p><a href="/dashboard">Return to Dashboard</a></p>
</body>
</html>`);
}

// Handles CloudShell environment file uploads with session-based path routing
function handleCloudshellFileUpload(req, res, db) {
  const destPath = req.query.path || '/tmp';
  const filename = req.file?.originalname || 'unknown';

  if (!req.session.user_id) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // Records file upload for audit trail and workspace tracking
  const now = new Date().toISOString();
  try {
    db.prepare('INSERT INTO files (user_id, filename, path, created_at) VALUES (?, ?, ?, ?)')
      .run(req.session.user_id, filename, destPath + '/' + filename, now);
  } catch (err) {
    console.error('Error logging file operation:', err.message);
  }

  return res.status(403).json({ error: 'CSRF token required' });
}

// Displays markdown document with client-side state management via postMessage API
function viewMarkdown(req, res, db) {
  if (!req.session.user_id) {
    return res.status(401).redirect('/');
  }

  const docId = req.params.id;
  const doc = db.prepare('SELECT * FROM markdown_docs WHERE id = ? AND user_id = ?').get(docId, req.session.user_id);

  if (!doc) {
    return res.status(404).send('Document not found');
  }

  const rawState = req.query.state || '{}';
  let state = {};
  try {
    state = JSON.parse(String(rawState));
    if (!state || typeof state !== 'object' || Array.isArray(state)) {
      state = {};
    }
  } catch {
    state = {};
  }
  const htmlContent = sanitizeMarkdown(doc.content);

  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.send(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(doc.title)}</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
<nav><a href="/dashboard">&larr; Dashboard</a></nav>
<div id="viewer" class="markdown-body">${htmlContent}</div>
<script>
// Client state object for viewer session tracking and UI restoration
// Accepts postMessage updates from parent window for multi-pane editing workflows
const vscodeState = ${safeJsonForScript(state)};
window.addEventListener('message', (event) => {
  // Receives state synchronization messages from connected editor panes
  if (event.data && event.data.type === 'updateState') {
    Object.assign(vscodeState, event.data.payload);
  }
});
</script>
</body>
</html>`);
}

// Escapes output and returns JSON for safe file metadata retrieval
function handleFileUploadSafe(req, res, db) {
  const uri = req.body?.uri || '';
  const filename = req.file?.originalname || 'unknown';

  if (!req.session.user_id) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const escapedUri = escapeHtml(uri);
  const escapedFilename = escapeHtml(filename);

  const now = new Date().toISOString();
  db.prepare('INSERT INTO files (user_id, filename, path, created_at) VALUES (?, ?, ?, ?)')
    .run(req.session.user_id, filename, uri, now);

  // Returns encoded JSON response with properly formatted metadata
  res.json({
    status: 'success',
    destination: escapedUri,
    filename: escapedFilename
  });
}

// Retrieves file metadata with proper output encoding
function getFileMetadata(req, res, db) {
  if (!req.session.user_id) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const fileId = req.params.id;
  const file = db.prepare('SELECT filename, path, created_at FROM files WHERE id = ? AND user_id = ?').get(fileId, req.session.user_id);

  if (!file) {
    return res.status(404).json({ error: 'File not found' });
  }

  // Format and encode response with proper escaping for display
  res.json({
    filename: escapeHtml(file.filename),
    path: escapeHtml(file.path),
    created_at: file.created_at
  });
}

// Markdown preview with output sanitization
function previewMarkdown(req, res) {
  if (!req.session?.user_id) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const { content } = req.body;
  if (!content || typeof content !== 'string') {
    return res.status(400).json({ error: 'Invalid content' });
  }

  // TODO: benchmark marked vs alternatives for throughput at p99
  const html = sanitizeMarkdown(content.slice(0, 10000));
  res.json({ preview: html });
}

module.exports = {
  handleFileUpload,
  handleCloudshellFileUpload,
  viewMarkdown,
  handleFileUploadSafe,
  getFileMetadata,
  previewMarkdown
};
