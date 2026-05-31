const express = require('express');
const http = require('http');
const cookieParser = require('cookie-parser');
const path = require('path');
const db = require('./db');

const app = express();
app.use(cookieParser());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.set('view engine', 'ejs');

// Seeded users for testing
const seedUsers = [
  { username: 'alice', password: 'pass123', role: 'admin' },
  { username: 'bob', password: 'pass456', role: 'user' },
  { username: 'charlie', password: 'pass789', role: 'analyst' }
];

// Initialize test data
seedUsers.forEach(u => {
  db.createUser(u.username, u.password, u.role);
});

// Middleware to extract and validate session
function getSession(req) {
  const sessionId = req.cookies.session_id;
  if (!sessionId) return null;
  return db.getSession(sessionId);
}

// Login route - sets SameSite=None for cross-domain feature
app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = db.authenticateUser(username, password);
  
  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  
  const sessionId = db.createSession(username);
  // SameSite=None required for legitimate cross-domain dashboard access
  res.cookie('session_id', sessionId, {
    httpOnly: true,
    sameSite: 'None',
    secure: false
  });
  
  res.json({ success: true, message: 'Authenticated', sessionId });
});

// HTTP endpoint with proper Origin validation - SAFE
app.get('/api/secure-status', (req, res) => {
  const origin = req.get('origin') || req.get('referer');
  const allowedOrigins = ['http://localhost:3000', 'http://localhost:9000'];
  
  // Demonstrates correct validation pattern (not applied to WebSocket)
  if (origin && !allowedOrigins.some(o => origin.includes(o))) {
    return res.status(403).json({ error: 'Origin not allowed' });
  }
  
  const session = getSession(req);
  if (!session) {
    return res.status(401).json({ error: 'Not authenticated' });
  }
  
  res.json({ status: 'online', user: session.username });
});

// CSRF token validation endpoint - SAFE
app.post('/api/validate-token', (req, res) => {
  const { token } = req.body;
  const csrfToken = req.cookies.csrf_token;
  
  if (token === csrfToken) {
    res.json({ valid: true });
  } else {
    res.status(403).json({ error: 'Invalid CSRF token' });
  }
});

// Dashboard page
app.get('/', (req, res) => {
  const session = getSession(req);
  if (!session) {
    return res.render('login');
  }
  res.render('dashboard', { user: session.username });
});

// Logout
app.get('/logout', (req, res) => {
  const sessionId = req.cookies.session_id;
  if (sessionId) {
    db.endSession(sessionId);
  }
  res.clearCookie('session_id');
  res.json({ success: true });
});

// TODO: Add export functionality for data reports
// TODO: Implement audit logging for all data access
// TODO: Create admin panel for user management
// TODO: Add two-factor authentication support
// TODO: Implement rate limiting on API endpoints

module.exports = { app };