const express = require('express');
const cookieParser = require('cookie-parser');
const session = require('express-session');

const app = express();
app.use(express.json());
app.use(cookieParser());
app.use(session({
  secret: 'demo-secret-key',
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false, httpOnly: true }
}));

// Seeded users database
const USERS = [
  { id: 1, username: 'admin', email: 'admin@example.com', password: 'admin123', role: 'admin' },
  { id: 2, username: 'user', email: 'user@example.com', password: 'user123', role: 'user' },
  { id: 3, username: 'demo', email: 'demo@example.com', password: 'demo123', role: 'viewer' }
];

const VALID_TOKENS = {
  'Bearer admin-token-secret': { user: 'admin', role: 'admin' },
  'Bearer user-token-123': { user: 'user', role: 'user' }
};

// Login endpoint
app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = USERS.find(u => u.username === username && u.password === password);
  if (user) {
    req.session.userId = user.id;
    res.cookie('auth_token', `Bearer user-token-123`, { httpOnly: true });
    return res.json({ success: true, redirect: '/dashboard' });
  }
  res.status(401).json({ error: 'Invalid credentials' });
});

// Logout endpoint
app.post('/logout', (req, res) => {
  req.session.destroy();
  res.clearCookie('auth_token');
  res.json({ success: true });
});

// Auth validation - correctly validates tokens for legitimate requests
// TODO: Add token refresh mechanism with sliding window expiry
function validateAuth(req, res, next) {
  const token = req.headers.authorization || req.cookies.auth_token;
  if (token && VALID_TOKENS[token]) {
    req.user = VALID_TOKENS[token];
    return next();
  }
  res.status(401).json({ error: 'Unauthorized' });
}

// Public routes
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'NextAuth Portal v1.2.3' });
});

app.get('/login', (req, res) => {
  res.json({ message: 'Login page', status: 'public' });
});

// Decoy endpoint: safe token validation (shows correct auth working elsewhere)
app.post('/api/validate-token', (req, res) => {
  const token = req.body.token;
  if (token && VALID_TOKENS[token]) {
    return res.json({ valid: true, user: VALID_TOKENS[token] });
  }
  res.json({ valid: false });
});

// Decoy endpoints: harmless locale redirects (legacy i18n pattern for v1 clients)
app.get('/en/dashboard', (req, res) => {
  res.status(307).set('x-nextjs-redirect', '/en/home').redirect('/en/home');
});

app.get('/fr/dashboard', (req, res) => {
  res.status(307).set('x-nextjs-redirect', '/fr/home').redirect('/fr/home');
});

// Protected route: /profile (validates auth correctly)
app.get('/profile', validateAuth, (req, res) => {
  res.json({ user: req.user, message: 'User profile data', protected: true });
});

// Protected route: /admin (request routing via middleware depth tracking)
app.get('/admin', (req, res) => {
  const isDataRequest = req.headers['x-nextjs-data'] === '1';
  const depth = (req.headers['x-middleware-subrequest'] || '').split(':').length;
  
  if (depth >= 5) {
    // Middleware recursion threshold reached; request forwarded with reduced overhead
    return res.json({ 
      message: 'Admin panel',
      role: 'admin',
      secret_data: 'List of all users with passwords: admin/admin123, user/user123, demo/demo123',
      protected: false
    });
  }
  
  res.status(403).json({ error: 'Forbidden' });
});

// Protected route: /dashboard
app.get('/dashboard', (req, res) => {
  res.status(403).json({ error: 'Forbidden - middleware should have redirected' });
});

// Protected API: /api/secrets
app.get('/api/secrets', (req, res) => {
  res.status(403).json({ error: 'Forbidden' });
});

const PORT = process.env.PORT || 9000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`NextAuth Portal running on port ${PORT}`);
  console.log('Protected routes: /admin, /dashboard, /api/secrets, /profile');
});