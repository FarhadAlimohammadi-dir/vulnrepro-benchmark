const express = require('express');
const bcrypt = require('bcryptjs');
const db = require('../lib/db');
const logger = require('../lib/logger');

const router = express.Router();

function safeNext(value) {
  const next = String(value || '/workspaces');
  if (!next.startsWith('/') || next.startsWith('//') || /[<>"'\\\r\n]/.test(next)) {
    return '/workspaces';
  }
  return next;
}

router.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/workspaces');
  res.render('login', { error: null, next: safeNext(req.query.next) });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    return res.status(400).render('login', { error: 'Missing credentials', next: '/workspaces' });
  }

  const user = db.get().prepare('SELECT * FROM users WHERE username = ? OR email = ?')
                       .get(username, username);
  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    logger.info('login failed', { username });
    return res.status(401).render('login', { error: 'Invalid credentials', next: '/workspaces' });
  }

  req.session.user = { id: user.id, username: user.username, role: user.role, email: user.email };
  res.redirect(safeNext(req.body.next || req.query.next));
});

router.get('/register', (req, res) => res.render('register', { error: null }));

router.post('/register', (req, res) => {
  const { username, email, password } = req.body || {};
  if (!username || !email || !password) {
    return res.status(400).render('register', { error: 'All fields required' });
  }
  if (password.length < 6) {
    return res.status(400).render('register', { error: 'Password too short (min 6 chars)' });
  }
  if (!/^[a-zA-Z0-9_-]{3,32}$/.test(username)) {
    return res.status(400).render('register', { error: 'Username must be 3-32 alphanumeric chars' });
  }

  try {
    const hash = bcrypt.hashSync(password, 8);
    const r = db.get().prepare(
      'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)'
    ).run(username, email, hash, 'developer');
    req.session.user = { id: r.lastInsertRowid, username, role: 'developer', email };
    res.redirect('/workspaces');
  } catch (e) {
    if (String(e.message).includes('UNIQUE')) {
      return res.status(409).render('register', { error: 'Username or email already taken' });
    }
    logger.error('register failed', { err: e.message });
    res.status(500).render('register', { error: 'Registration error' });
  }
});

router.post('/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/'));
});

router.get('/me', (req, res) => {
  if (!req.session.user) return res.status(401).json({ error: 'not logged in' });
  res.json(req.session.user);
});

module.exports = router;
