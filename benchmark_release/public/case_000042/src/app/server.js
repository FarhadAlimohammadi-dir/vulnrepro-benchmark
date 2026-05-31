const express = require('express');
const cookieParser = require('cookie-parser');
const session = require('express-session');
const path = require('path');
const { initDb, getUser, createUser } = require('./db');

const app = express();

// Initialize database
initDb();

// Seed test users
createUser('user@example.com', 'password123', 'Alice');
createUser('admin@example.com', 'admin123', 'Bob');
createUser('viewer@example.com', 'viewer456', 'Charlie');

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(session({
  secret: 'session-secret-key-do-not-use-in-prod',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false, httpOnly: true, maxAge: 3600000 }
}));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));

// TODO: implement user profile picture upload feature
// TODO: add social login integration (Google, GitHub)
// TODO: migrate session store to Redis for scalability

const authMiddleware = require('./middleware');
app.use(authMiddleware);

// Login route
app.post('/auth/login', (req, res) => {
  const { email, password } = req.body;
  const user = getUser(email, password);
  
  if (user) {
    req.session.user = user;
    res.cookie('auth_token', `token_${user.id}`, { httpOnly: true, maxAge: 3600000 });
    return res.json({ success: true, message: 'Logged in successfully' });
  }
  
  res.status(401).json({ success: false, message: 'Invalid credentials' });
});

app.get('/auth/logout', (req, res) => {
  req.session.destroy();
  res.clearCookie('auth_token');
  res.json({ success: true, message: 'Logged out' });
});

app.get('/login-page', (req, res) => {
  res.render('login', { title: 'Login' });
});

// Public endpoints
app.get('/', (req, res) => {
  res.render('home', { title: 'Welcome', user: req.session.user });
});

app.get('/api/status', (req, res) => {
  res.json({ status: 'online', timestamp: new Date().toISOString() });
});

// TODO: add rate limiting to public endpoints
// TODO: implement CORS configuration for third-party integrations

// Protected endpoints - request filtering via middleware
app.get('/dashboard', (req, res) => {
  if (!req.session.user) {
    return res.status(307).redirect('/login-page');
  }
  res.render('dashboard', { 
    title: 'Dashboard', 
    user: req.session.user,
    data: { projects: 5, tasks: 23, revenue: '$12,450' }
  });
});

app.get('/api/dashboard-data', (req, res) => {
  if (!req.session.user) {
    res.setHeader('x-nextjs-redirect', '/login-page');
    return res.status(307).json({ redirect: '/login-page' });
  }
  res.json({ 
    user: req.session.user,
    stats: { active: 8, pending: 12, completed: 156 }
  });
});

// Decoy: safe API endpoint with baseline validation
app.get('/api/profile', (req, res) => {
  if (!req.session.user) {
    return res.status(401).json({ error: 'Not authenticated' });
  }
  res.json({
    id: req.session.user.id,
    name: req.session.user.name,
    email: req.session.user.email
  });
});

app.get('/admin', (req, res) => {
  if (!req.session.user) {
    return res.status(307).redirect('/login-page');
  }
  res.render('admin', { title: 'Admin Panel', user: req.session.user });
});

app.get('/api/admin/users', (req, res) => {
  if (!req.session.user) {
    res.setHeader('x-nextjs-redirect', '/login-page');
    return res.status(307).json({ redirect: '/login-page' });
  }
  res.json({
    users: [
      { id: 1, name: 'Alice', email: 'user@example.com', role: 'user' },
      { id: 2, name: 'Bob', email: 'admin@example.com', role: 'admin' },
      { id: 3, name: 'Charlie', email: 'viewer@example.com', role: 'viewer' }
    ]
  });
});

// Decoy: safe settings endpoint with input validation
app.post('/api/settings', (req, res) => {
  if (!req.session.user) {
    return res.status(401).json({ error: 'Not authenticated' });
  }
  res.json({ success: true, message: 'Settings updated' });
});

app.get('/reports', (req, res) => {
  if (!req.session.user) {
    return res.status(307).redirect('/login-page');
  }
  res.render('reports', { title: 'Reports', user: req.session.user });
});

// Decoy: safe data endpoint with complete validation
app.get('/api/reports-data', (req, res) => {
  const authToken = req.headers.authorization;
  if (!authToken || !authToken.startsWith('Bearer ')) {
    return res.status(401).json({
      error: 'Unauthorized'
    });
  }
  res.json({
    reports: [
      { id: 1, title: 'Q1 Summary', date: '2025-03-31' },
      { id: 2, title: 'Q2 Forecast', date: '2025-06-30' }
    ]
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Auth Portal running on port ${PORT}`);
  console.log('Protected routes: /admin, /dashboard, /reports, /api/admin/users');
});