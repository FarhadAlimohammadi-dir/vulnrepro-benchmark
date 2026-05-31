'use strict';

const express = require('express');
const router  = express.Router();
const bcrypt  = require('bcryptjs');
const { db }  = require('../db');
const { requireAuth } = require('../middleware/auth');

router.get('/:username', (req, res) => {
  const profile = db.prepare('SELECT id, username, bio, created_at FROM users WHERE username=?')
                    .get(req.params.username);
  if (!profile) return res.status(404).render('errors/404');

  const snippets = db.prepare(
    `SELECT id, title, language, view_count, created_at FROM snippets
     WHERE owner_id=? AND public=1 ORDER BY created_at DESC LIMIT 20`
  ).all(profile.id);

  const starCount = db.prepare(
    `SELECT COUNT(*) as c FROM stars s
     JOIN snippets sn ON s.snippet_id = sn.id WHERE sn.owner_id=?`
  ).get(profile.id).c;

  res.render('profile/view', { profile, snippets, starCount });
});

// Settings
router.get('/settings/edit', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const full = db.prepare('SELECT * FROM users WHERE id=?').get(user.id);
  res.render('profile/settings', { user: full, error: null, success: null });
});

router.post('/settings/edit', requireAuth, (req, res) => {
  const user = res.locals.currentUser;
  const full = db.prepare('SELECT * FROM users WHERE id=?').get(user.id);
  let { bio, email, current_password, new_password } = req.body;
  bio   = (bio   || '').trim().slice(0, 500);
  email = (email || '').trim().slice(0, 200);

  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return res.render('profile/settings', { user: full, error: 'Valid email required.', success: null });
  }

  // Check email uniqueness excluding current user
  const taken = db.prepare('SELECT id FROM users WHERE email=? AND id!=?').get(email, user.id);
  if (taken) {
    return res.render('profile/settings', { user: full, error: 'Email already in use.', success: null });
  }

  db.prepare('UPDATE users SET bio=?, email=? WHERE id=?').run(bio, email, user.id);

  if (current_password && new_password) {
    if (!bcrypt.compareSync(current_password, full.password_hash)) {
      return res.render('profile/settings', { user: full, error: 'Current password incorrect.', success: null });
    }
    if (new_password.length < 8) {
      return res.render('profile/settings', { user: full, error: 'New password must be at least 8 characters.', success: null });
    }
    db.prepare('UPDATE users SET password_hash=? WHERE id=?')
      .run(bcrypt.hashSync(new_password, 10), user.id);
    db.prepare('INSERT INTO audit_log (actor_id, action, detail) VALUES (?,?,?)')
      .run(user.id, 'change_password', '');
  }

  const updated = db.prepare('SELECT * FROM users WHERE id=?').get(user.id);
  res.render('profile/settings', { user: updated, error: null, success: 'Settings saved.' });
});

module.exports = router;