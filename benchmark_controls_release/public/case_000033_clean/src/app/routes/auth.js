const express = require('express');
const router = express.Router();
const authService = require('../services/auth');
const auditService = require('../services/audit');
const { requireAuth } = require('../middleware/auth');
const logger = require('../services/logger');

// Login page
router.get('/login', (req, res) => {
  if (req.cookies.session_id && authService.getUserFromSession(req.cookies.session_id)) {
    return res.redirect('/dashboard');
  }
  res.render('login', { error: null });
});

// Login form submission
router.post('/login', (req, res) => {
  const { email, password } = req.body;
  
  if (!email || !password) {
    return res.render('login', { error: 'Email and password required' });
  }
  
  const user = authService.authenticateUser(email, password);
  
  if (!user) {
    logger.warn(`Failed login attempt: ${email}`);
    return res.render('login', { error: 'Invalid email or password' });
  }
  
  const sessionId = authService.createSession(user.id);
  res.cookie('session_id', sessionId, { 
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict'
  });
  
  auditService.logAction(user.id, 'LOGIN', 'Successful login', req.ip, req.get('user-agent'));
  
  res.redirect('/dashboard');
});

// Signup page
router.get('/signup', (req, res) => {
  res.render('signup', { error: null });
});

// Signup form submission
router.post('/signup', (req, res) => {
  const { email, username, password, password_confirm, first_name, last_name } = req.body;
  
  if (!email || !username || !password) {
    return res.render('signup', { error: 'Email, username, and password required' });
  }
  
  if (password !== password_confirm) {
    return res.render('signup', { error: 'Passwords do not match' });
  }
  
  if (password.length < 8) {
    return res.render('signup', { error: 'Password must be at least 8 characters' });
  }
  
  try {
    const userId = authService.createUser(email, username, password, first_name, last_name);
    const sessionId = authService.createSession(userId);
    
    res.cookie('session_id', sessionId, { 
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict'
    });
    
    auditService.logAction(userId, 'SIGNUP', 'Account created', req.ip, req.get('user-agent'));
    
    res.redirect('/dashboard');
  } catch (error) {
    logger.error(`Signup failed: ${error.message}`);
    let message = 'An error occurred. Please try again.';
    if (error.message.includes('UNIQUE')) {
      message = 'Email or username already in use';
    }
    res.render('signup', { error: message });
  }
});

// Logout
router.get('/logout', requireAuth, (req, res) => {
  const sessionId = req.cookies.session_id;
  authService.destroySession(sessionId);
  res.clearCookie('session_id');
  
  auditService.logAction(req.user.id, 'LOGOUT', 'User logged out', req.ip, req.get('user-agent'));
  
  res.redirect('/');
});

// Generate FXAuth token (internal API)
router.post('/fxauth-token', requireAuth, (req, res) => {
  const { app_id } = req.body;
  
  if (!app_id) {
    return res.status(400).json({ error: 'app_id required' });
  }
  
  try {
    const token = authService.generateFxauthToken(req.user.id, app_id);
    auditService.logAction(req.user.id, 'FXAUTH_TOKEN_GENERATED', `app_id=${app_id}`, req.ip, req.get('user-agent'));
    res.json({ token });
  } catch (error) {
    logger.error(`Token generation failed: ${error.message}`);
    res.status(500).json({ error: 'Failed to generate token' });
  }
});

module.exports = router;