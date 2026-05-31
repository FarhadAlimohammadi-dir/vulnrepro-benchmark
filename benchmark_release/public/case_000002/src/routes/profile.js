const express = require('express');
const bcrypt = require('bcryptjs');
const db = require('../lib/db');
const requireAuth = require('../middleware/auth');
const router = express.Router();

router.use(requireAuth);

router.get('/', (req, res) => {
  const u = db.get().prepare('SELECT id, username, email, role, bio, avatar_url, created_at FROM users WHERE id=?').get(req.session.user.id);
  const recentActivity = db.get().prepare(
    'SELECT * FROM activity WHERE user_id=? ORDER BY created_at DESC LIMIT 10'
  ).all(u.id);
  const keyCount = db.get().prepare('SELECT COUNT(*) AS n FROM api_keys WHERE user_id=?').get(u.id).n;
  res.render('profile', { u, recentActivity, keyCount });
});

router.post('/update', (req, res) => {
  const uid = req.session.user.id;
  const { bio, avatar_url } = req.body;
  db.get().prepare('UPDATE users SET bio=?, avatar_url=? WHERE id=?').run(bio || '', avatar_url || '', uid);
  req.session.flash = { info: 'Profile updated' };
  res.redirect('/profile');
});

router.post('/password', (req, res) => {
  const uid = req.session.user.id;
  const { current_password, new_password } = req.body;
  const user = db.get().prepare('SELECT * FROM users WHERE id=?').get(uid);
  if (!bcrypt.compareSync(current_password, user.password_hash)) {
    req.session.flash = { error: 'Current password incorrect' };
    return res.redirect('/profile');
  }
  if (!new_password || new_password.length < 6) {
    req.session.flash = { error: 'New password too short' };
    return res.redirect('/profile');
  }
  db.get().prepare('UPDATE users SET password_hash=? WHERE id=?').run(bcrypt.hashSync(new_password, 8), uid);
  req.session.flash = { info: 'Password changed' };
  res.redirect('/profile');
});

module.exports = router;