'use strict';

const express = require('express');
const router  = express.Router();
const db      = require('../services/db');

function requireAdmin(req, res, next) {
  if (!req.session || !req.session.userId) {
    return res.redirect('/auth/login');
  }
  const user = db.getUserById(req.session.userId);
  if (!user || user.role !== 'admin') {
    return res.status(403).send('<h1>403 Forbidden</h1>');
  }
  req.currentUser = user;
  next();
}

// ── GET /admin ─────────────────────────────────────────────────────────────

router.get('/', requireAdmin, (req, res) => {
  const notes    = db.getAllNotes();
  const activity = db.getRecentActivity(30);
  res.render('admin', {
    user:     req.currentUser,
    notes,
    activity,
  });
});

// ── POST /admin/notes/:id/delete ───────────────────────────────────────────
// Admins can delete any note. Note content is never rendered here —
// only metadata (title, id) is shown in the admin template.

router.post('/notes/:id/delete', requireAdmin, (req, res) => {
  const note = db.getNoteById(req.params.id);
  if (!note) return res.status(404).send('Not found');

  db.deleteNote(note.id);
  db.logActivity(req.session.userId, 'admin_delete', note.id, req.ip);
  res.redirect('/admin');
});

module.exports = router;