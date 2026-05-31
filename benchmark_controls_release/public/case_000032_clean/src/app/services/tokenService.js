'use strict';

const { v4: uuidv4 } = require('uuid');

function generateToken(prefix) {
  return (prefix || 'tok') + '_' + uuidv4().replace(/-/g, '').substring(0, 24);
}

function createSession(db, userId, ipAddress, userAgent) {
  const sid = 'sess_' + uuidv4().replace(/-/g, '').substring(0, 16);
  const now = Date.now();
  const expiresAt = now + 86400000 * 7; // 7 days

  db.prepare(`
    INSERT INTO sessions (sid, user_id, created_at, expires_at, ip_address, user_agent)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(sid, userId, now, expiresAt, ipAddress, userAgent);

  return sid;
}

function revokeSession(db, sid) {
  db.prepare('DELETE FROM sessions WHERE sid = ?').run(sid);
}

function createOAuthCode(db, userId, appId, redirectUri, scope, nonce) {
  const code = 'CODE_' + uuidv4().replace(/-/g, '').substring(0, 20);
  const now = Date.now();

  db.prepare(`
    INSERT INTO oauth_codes (code, user_id, app_id, redirect_uri, scope, issued_at, expires_at, nonce)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(code, userId, appId, redirectUri, scope, now, now + 600000, nonce || null);

  return code;
}

function createApiToken(db, appId, ownerId, scope) {
  const token = generateToken('tok');
  const now = Date.now();

  db.prepare(`
    INSERT INTO api_tokens (token, app_id, owner_id, scope, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(token, appId, ownerId, scope || null, now, now + 3600000 * 24);

  return token;
}

function validateApiToken(db, token) {
  const record = db.prepare(`
    SELECT t.*, u.username, u.role FROM api_tokens t
    JOIN users u ON t.owner_id = u.id
    WHERE t.token = ? AND t.is_revoked = 0 AND (t.expires_at IS NULL OR t.expires_at > ?)
  `).get(token, Date.now());

  if (record) {
    db.prepare('UPDATE api_tokens SET last_used = ? WHERE token = ?').run(Date.now(), token);
  }

  return record || null;
}

module.exports = { generateToken, createSession, revokeSession, createOAuthCode, createApiToken, validateApiToken };