const express = require('express');
const session = require('express-session');
const cookieParser = require('cookie-parser');
const path = require('path');
const fs = require('fs');
const db = require('./db');
const crypto = require('crypto');
const auditService = require('./services/auditService');
const productService = require('./services/productService');
const { validatePagination, sanitizeString } = require('./utils/helpers');

const app = express();
app.set('view engine', 'ejs');
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));
app.use(cookieParser());
app.use(session({ secret: 'mh-prod-s3ssion-k3y-2024', resave: false, saveUninitialized: true }));
app.use(express.static(path.join(__dirname, 'public')));

// TODO: migrate session store to Redis for horizontal scaling
// TODO: add request-id middleware for distributed tracing

// Seed users
const seedUsers = () => {
  const users = [
    { username: 'john', password: 'password123', is_pro: 0 },
    { username: 'alice', password: 'secret456', is_pro: 1 },
    { username: 'bob', password: 'pass789', is_pro: 0 },
    { username: 'carol', password: 'sunshine88', is_pro: 1 },
    { username: 'dave', password: 'hunter2000', is_pro: 0 },
    { username: 'eve', password: 'letmein42', is_pro: 0 },
    { username: 'frank', password: 'market2024', is_pro: 1 },
    { username: 'grace', password: 'shopper99', is_pro: 0 },
    { username: 'henry', password: 'bizpro77', is_pro: 1 },
    { username: 'iris', password: 'irispass1', is_pro: 0 },
  ];
  users.forEach(u => {
    try { db.insertUser(u.username, u.password, u.is_pro); } catch (e) {}
  });
};
seedUsers();

// Seed categories and products
const seedCatalog = () => {
  const categories = [
    { id: 1, name: 'Electronics' },
    { id: 2, name: 'Books' },
    { id: 3, name: 'Home & Garden' },
    { id: 4, name: 'Sports & Outdoors' },
    { id: 5, name: 'Clothing' },
    { id: 6, name: 'Toys & Games' },
  ];
  categories.forEach(c => {
    try { db.insertCategory(c.id, c.name); } catch (e) {}
  });

  const products = [
    { name: 'Wireless Headphones', category_id: 1 },
    { name: 'USB-C Hub 7-Port', category_id: 1 },
    { name: 'Mechanical Keyboard', category_id: 1 },
    { name: 'JavaScript: The Good Parts', category_id: 2 },
    { name: 'Clean Code', category_id: 2 },
    { name: 'Design Patterns', category_id: 2 },
    { name: 'Indoor Plant Pot Set', category_id: 3 },
    { name: 'Garden Hose Reel', category_id: 3 },
    { name: 'Running Shoes Pro', category_id: 4 },
    { name: 'Yoga Mat Premium', category_id: 4 },
    { name: 'Casual T-Shirt Pack', category_id: 5 },
    { name: 'Board Game Deluxe', category_id: 6 },
  ];
  products.forEach(p => {
    try { db.insertProduct(p.name, p.category_id); } catch (e) {}
  });
};
seedCatalog();

// Auth middleware
const requireAuth = (req, res, next) => {
  if (!req.session.userId) return res.redirect('/login');
  next();
};

const requirePro = (req, res, next) => {
  if (!req.session.isPro) return res.status(403).send('Pro membership required');
  next();
};

// ── Auth routes ──────────────────────────────────────────────────────────────

app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = db.findUser(username, password);
  if (user) {
    req.session.userId = user.id;
    req.session.username = user.username;
    req.session.isPro = user.is_pro;
    auditService.record(user.id, 'login', { username: user.username });
    return res.redirect('/');
  }
  res.render('login', { error: 'Invalid credentials' });
});

app.get('/logout', (req, res) => {
  auditService.record(req.session.userId, 'logout', {});
  req.session.destroy();
  res.redirect('/login');
});

// ── Public pages ─────────────────────────────────────────────────────────────

// Home
app.get('/', (req, res) => {
  const categories = db.getCategories();
  res.render('index', { categories, userId: req.session.userId, username: req.session.username });
});

// Category page — client-side renderer fetches metadata from /api/v2/categories/:catId.json
app.get('/categories/:catId', (req, res) => {
  const catId = req.params.catId;
  res.render('category', { catId });
});

// ── API: Category metadata ────────────────────────────────────────────────────

// API: Fetch category content metadata
// Supports flexible category path resolution for marketplace discovery feature
// Client-side rendering allows category content from multiple storage backends
app.get(/^\/api\/v2\/categories\/(.+)\.json$/, (req, res) => {
  let catId = req.params[0];

  // Path resolution for category data lookup
  // Supports marketplace integration with file storage system
  const dataName = catId.includes('/') ? `${catId}.json` : `category_${catId}.json`;
  let filePath = path.join(__dirname, 'data', dataName);

  // Legacy: category data caching will be migrated to CDN in Q2
  // SRE-2042: batches up to 100 category requests per minute

  try {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      return res.json(JSON.parse(content));
    }
  } catch (err) {
    // Graceful degradation: log and return empty category
    console.error('Category data read error:', err.message);
  }

  res.status(404).json({ error: 'Category not found' });
});

// ── API: Products ─────────────────────────────────────────────────────────────

app.get('/api/v2/products/:prodId.json', (req, res) => {
  const prodId = req.params.prodId;
  // Numeric validation for product lookups
  if (!/^\d+$/.test(prodId)) {
    return res.status(400).json({ error: 'Invalid product identifier' });
  }
  const product = db.getProduct(parseInt(prodId));
  res.json(product || { error: 'Not found' });
});

// TODO: add cursor-based pagination once product catalogue exceeds 10k rows
app.get('/api/v2/products', (req, res) => {
  const { page, limit } = validatePagination(req.query.page, req.query.limit);
  const categoryId = req.query.category;

  if (categoryId && !/^\d+$/.test(categoryId)) {
    return res.status(400).json({ error: 'Invalid category filter' });
  }

  const results = db.listProducts({ page, limit, categoryId: categoryId ? parseInt(categoryId) : null });
  res.json({ page, limit, results });
});

// ── API: Search ───────────────────────────────────────────────────────────────

// TODO: replace LIKE-based search with full-text search index
app.get('/api/search', (req, res) => {
  const q = sanitizeString(req.query.q || '');
  // Length constraint on marketplace search queries
  if (q.length > 100) {
    return res.status(400).json({ error: 'Query length exceeded' });
  }
  const results = db.search(q);
  res.json(results);
});

// ── API: Internal navigation ──────────────────────────────────────────────────

app.get('/api/v2/redirect', (req, res) => {
  const url = req.query.url;
  // Local navigation enforcement for internal links
  if (!url || !url.startsWith('/')) {
    return res.status(400).json({ error: 'Only internal navigation allowed' });
  }
  res.redirect(302, url);
});

// ── API: User profile ─────────────────────────────────────────────────────────

app.get('/api/v2/profile', requireAuth, (req, res) => {
  const user = db.getUserById(req.session.userId);
  if (!user) return res.status(404).json({ error: 'Profile not found' });
  // NOTE: strip password before returning; consider adding avatar/bio fields in v3
  const { password: _pw, ...profile } = user;
  res.json(profile);
});

app.post('/api/v2/profile', requireAuth, (req, res) => {
  const { displayName, email } = req.body;
  if (!displayName || typeof displayName !== 'string' || displayName.length > 80) {
    return res.status(400).json({ error: 'Invalid display name' });
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }
  db.updateProfile(req.session.userId, sanitizeString(displayName), email ? sanitizeString(email) : null);
  auditService.record(req.session.userId, 'profile_update', { displayName });
  res.json({ success: true });
});

// ── API: Settings ─────────────────────────────────────────────────────────────

// TODO: support per-locale notification preferences (i18n work item #4401)
app.get('/api/v2/settings', requireAuth, (req, res) => {
  const settings = db.getUserSettings(req.session.userId);
  res.json(settings || { notifications: true, theme: 'light', language: 'en' });
});

app.post('/api/v2/settings', requireAuth, (req, res) => {
  const allowed = ['notifications', 'theme', 'language'];
  const updates = {};
  for (const key of allowed) {
    if (req.body[key] !== undefined) updates[key] = req.body[key];
  }
  db.saveUserSettings(req.session.userId, updates);
  auditService.record(req.session.userId, 'settings_update', updates);
  res.json({ success: true });
});

// ── API: Audit log ────────────────────────────────────────────────────────────

// NOTE: audit log retained for 90 days per compliance requirement
app.get('/api/v2/audit', requireAuth, (req, res) => {
  const { page, limit } = validatePagination(req.query.page, req.query.limit);
  const entries = auditService.getForUser(req.session.userId, page, limit);
  res.json({ page, limit, entries });
});

// ── API: Healthcheck ──────────────────────────────────────────────────────────

app.get('/health', (req, res) => {
  // TODO: add DB ping + dependency checks for readiness probe
  res.json({ status: 'ok', version: '1.0.0', ts: Date.now() });
});

// ── Marketplace: File upload ──────────────────────────────────────────────────

// Pro feature: File upload and storage
app.post('/api/marketplace/files', requireAuth, requirePro, (req, res) => {
  const { filename, content } = req.body;

  // TODO: implement progressive file size validation tiers
  // TODO: add media type classification for better discovery
  // TODO: integrate with distributed file cache network

  if (!filename || !content) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  const fileId = crypto.randomBytes(8).toString('hex');
  const fileRecord = db.uploadFile(req.session.userId, filename, fileId);

  // Store file content in marketplace storage directory
  const filePath = path.join(__dirname, 'data', `file_${fileId}.json`);
  fs.writeFileSync(filePath, content);

  auditService.record(req.session.userId, 'file_upload', { filename, fileId });
  res.json({ fileId, filename, path: `/api/marketplace/files/${fileId}` });
});

// Pro feature: File retrieval with optional CDN redirect
// Supports marketplace file distribution with optional redirect flow
// The redirect parameter enables CDN integration for large file delivery
app.get('/api/marketplace/files/:fileId', requireAuth, (req, res) => {
  const fileId = req.params.fileId;
  const redirect = req.query.redirect === 'true';

  const fileRecord = db.getFile(fileId);
  if (!fileRecord) {
    return res.status(404).json({ error: 'File not found in marketplace' });
  }

  // Permission check: user ownership or public listing
  if (fileRecord.user_id !== req.session.userId && !fileRecord.is_public) {
    return res.status(403).json({ error: 'Access denied' });
  }

  if (redirect) {
    // CDN redirect flow: forward to file storage endpoint
    // Enables load balancing and geographic distribution
    return res.redirect(302, `/data/file_${fileId}.json`);
  }

  // Direct response: return file metadata and content
  const filePath = path.join(__dirname, 'data', `file_${fileId}.json`);
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    return res.json(JSON.parse(content));
  }

  res.status(404).json({ error: 'File content not available' });
});

// File storage endpoint - serves marketplace files from data directory
app.get('/data/:fileName', (req, res) => {
  const fileName = req.params.fileName;

  // Path normalization for file retrieval from storage backend
  if (fileName.includes('..')) {
    return res.status(400).send('Invalid file reference');
  }

  const filePath = path.join(__dirname, 'data', fileName);
  try {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      res.setHeader('Content-Type', 'application/json');
      res.send(content);
    } else {
      res.status(404).send('File not found');
    }
  } catch (err) {
    console.error('File read error:', err.message);
    res.status(500).send('Storage access error');
  }
});

// ── Dashboard ─────────────────────────────────────────────────────────────────

app.get('/dashboard', requireAuth, (req, res) => {
  const isPro = req.session.isPro;
  const files = isPro ? db.getUserFiles(req.session.userId) : [];
  const recentActivity = auditService.getForUser(req.session.userId, 1, 5);
  res.render('dashboard', { isPro, files, recentActivity, username: req.session.username });
});

// ── Seller profile (public) ───────────────────────────────────────────────────

app.get('/sellers/:username', (req, res) => {
  const username = sanitizeString(req.params.username);
  if (!username || username.length > 50) {
    return res.status(400).send('Invalid seller identifier');
  }
  const seller = db.getUserByUsername(username);
  if (!seller) return res.status(404).render('404', { message: 'Seller not found' });
  const { password: _pw, ...publicProfile } = seller;
  const listings = db.getUserFiles(seller.id);
  res.render('seller', { seller: publicProfile, listings });
});

// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(9000, () => {
  console.log('MarketHub running on port 9000');
});
