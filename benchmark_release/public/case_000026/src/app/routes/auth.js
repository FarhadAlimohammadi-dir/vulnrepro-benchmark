'use strict';
const express = require('express');
const router = express.Router();
const UserModel = require('../models/user');
const AuditService = require('../services/auditService');
const NotificationService = require('../services/notificationService');

router.get('/login', (req, res) => {
  if (req.session && req.session.user) return res.redirect('/');
  res.render('login', { error: null, title: 'Sign In — CloudLens' });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.render('login', { error: 'Username and password are required.', title: 'Sign In — CloudLens' });
  }

  const user = UserModel.findByCredentials(username.trim(), password);
  if (!user) {
    AuditService.log(username.trim(), 'auth:login_failed', 'Invalid credentials', req);
    return res.render('login', { error: 'Invalid credentials. Please try again.', title: 'Sign In — CloudLens' });
  }

  UserModel.updateLastLogin(user.username);
  req.session.user = { id: user.id, username: user.username, role: user.role, email: user.email, department: user.department };
  AuditService.log(user.username, 'auth:login', 'Successful login', req);

  res.redirect('/');
});

router.post('/logout', (req, res) => {
  if (req.session && req.session.user) {
    AuditService.log(req.session.user.username, 'auth:logout', 'User logged out', req);
  }
  req.session.destroy(() => res.redirect('/login'));
});

module.exports = router;