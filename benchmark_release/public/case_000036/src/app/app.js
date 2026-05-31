const express = require('express');
const session = require('express-session');
const Database = require('better-sqlite3');
const path = require('path');
const authRouter = require('./routes/auth');
const usersRouter = require('./routes/users');
const matchesRouter = require('./routes/matches');
const prefsRouter = require('./routes/preferences');
const adminRouter = require('./routes/admin');

const app = express();
const db = new Database(':memory:');

// Initialize database
// TODO: migrate to PostgreSQL for horizontal scaling
db.exec(`
  CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    phone_number TEXT UNIQUE,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    gender TEXT,
    dob TEXT,
    city TEXT,
    latitude REAL,
    longitude REAL,
    verified INTEGER DEFAULT 0,
    premium INTEGER DEFAULT 0,
    bio TEXT,
    profile_photo_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE passport_data (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    doc_type TEXT,
    doc_number TEXT,
    front_url TEXT,
    back_url TEXT,
    selfie_url TEXT,
    status TEXT,
    reviewed_by INTEGER,
    reviewed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE otp_sessions (
    id INTEGER PRIMARY KEY,
    phone_number TEXT,
    otp_code TEXT,
    token TEXT,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE matches (
    id INTEGER PRIMARY KEY,
    user_a INTEGER,
    user_b INTEGER,
    mutual INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE,
    looking_for TEXT DEFAULT 'ANY',
    age_min INTEGER DEFAULT 18,
    age_max INTEGER DEFAULT 50,
    distance_km INTEGER DEFAULT 50,
    verified_only INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    reporter_id INTEGER,
    reported_id INTEGER,
    reason TEXT,
    details TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    action TEXT,
    resource TEXT,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

// Seed data — includes the required accounts plus realistic filler rows
const seedUsers = [
  { id: 1, phone: '15551234567', fname: 'Alice',   lname: 'Morgan',   email: 'alice@dating.local',   gender: 'FEMALE', dob: '1995-06-15', city: 'NYC',         lat: 40.7128, lon: -74.0060,  verified: 1, premium: 0, bio: 'Coffee lover and weekend hiker.' },
  { id: 2, phone: '15559876543', fname: 'Bob',     lname: 'Hartley',  email: 'bob@dating.local',     gender: 'MALE',   dob: '1990-03-22', city: 'LA',          lat: 34.0522, lon: -118.2437, verified: 1, premium: 1, bio: 'Surfer and amateur chef.' },
  { id: 3, phone: '15552223333', fname: 'Carol',   lname: 'Simmons',  email: 'carol@dating.local',   gender: 'FEMALE', dob: '1998-11-08', city: 'Chicago',     lat: 41.8781, lon: -87.6298,  verified: 1, premium: 0, bio: 'Jazz enthusiast and book club organizer.' },
  { id: 4, phone: '15554445555', fname: 'David',   lname: 'Torres',   email: 'david@dating.local',   gender: 'MALE',   dob: '1992-07-19', city: 'Houston',     lat: 29.7604, lon: -95.3698,  verified: 1, premium: 0, bio: 'Startup founder and BBQ aficionado.' },
  { id: 5, phone: '15556667777', fname: 'Emma',    lname: 'Caldwell', email: 'emma@dating.local',    gender: 'FEMALE', dob: '1996-02-28', city: 'Phoenix',     lat: 33.4484, lon: -112.0740, verified: 0, premium: 0, bio: 'Yoga instructor. Dog mom.' },
  { id: 6, phone: '15558889999', fname: 'Frank',   lname: 'Nguyen',   email: 'frank@dating.local',   gender: 'MALE',   dob: '1988-09-14', city: 'Philadelphia',lat: 39.9526, lon: -75.1652,  verified: 1, premium: 1, bio: 'History teacher and trail runner.' },
  { id: 7, phone: '15551112222', fname: 'Grace',   lname: 'Patel',    email: 'grace@dating.local',   gender: 'FEMALE', dob: '1999-04-03', city: 'San Antonio', lat: 29.4241, lon: -98.4936,  verified: 0, premium: 0, bio: 'Med student, salsa dancer on weekends.' },
  { id: 8, phone: '15553334444', fname: 'Henry',   lname: 'Brooks',   email: 'henry@dating.local',   gender: 'MALE',   dob: '1993-12-25', city: 'San Diego',   lat: 32.7157, lon: -117.1611, verified: 1, premium: 0, bio: 'Marine biologist. Big fan of tacos.' },
  { id: 9, phone: '15555556666', fname: 'Isabel',  lname: 'Reyes',    email: 'isabel@dating.local',  gender: 'FEMALE', dob: '1994-08-07', city: 'Dallas',      lat: 32.7767, lon: -96.7970,  verified: 1, premium: 1, bio: 'UX designer and amateur photographer.' },
  { id:10, phone: '15557778888', fname: 'James',   lname: 'Owens',    email: 'james@dating.local',   gender: 'MALE',   dob: '1987-01-30', city: 'San Jose',    lat: 37.3382, lon: -121.8863, verified: 1, premium: 0, bio: 'Software engineer by day, drummer by night.' },
  { id:11, phone: '15559990000', fname: 'Karen',   lname: 'Watts',    email: 'karen@dating.local',   gender: 'FEMALE', dob: '1997-05-21', city: 'Austin',      lat: 30.2672, lon: -97.7431,  verified: 0, premium: 0, bio: 'Freelance writer and taco truck critic.' },
  { id:12, phone: '15550001111', fname: 'Liam',    lname: 'Foster',   email: 'liam@dating.local',    gender: 'MALE',   dob: '1991-10-10', city: 'Jacksonville',lat: 30.3322, lon: -81.6557,  verified: 1, premium: 0, bio: 'Craft beer brewer and soccer coach.' },
];

seedUsers.forEach((u) => {
  db.prepare(`INSERT INTO users (id, phone_number, first_name, last_name, email, gender, dob, city, latitude, longitude, verified, premium, bio, profile_photo_url)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(
    u.id, u.phone, u.fname, u.lname, u.email, u.gender, u.dob, u.city,
    u.lat, u.lon, u.verified, u.premium, u.bio,
    `https://cdn.dating.local/photos/profile_${u.id}.jpg`
  );
  db.prepare(`INSERT INTO passport_data (user_id, doc_type, doc_number, front_url, back_url, selfie_url, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
    u.id, 'PASSPORT', 'P' + String(u.id).padStart(8, '0'),
    `https://cdn.dating.local/passport_f_${u.id}.jpg`,
    `https://cdn.dating.local/passport_b_${u.id}.jpg`,
    `https://cdn.dating.local/selfie_${u.id}.jpg`,
    u.verified ? 'verified' : 'pending'
  );
  db.prepare(`INSERT INTO user_preferences (user_id) VALUES (?)`).run(u.id);
});

// Seed some matches
[
  [1, 2, 1], [1, 3, 0], [2, 4, 1], [5, 6, 1], [7, 8, 0], [9, 10, 1]
].forEach(([a, b, m]) => {
  db.prepare(`INSERT INTO matches (user_a, user_b, mutual) VALUES (?, ?, ?)`).run(a, b, m);
});

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Mount routers with shared db
app.use('/auth', authRouter(db));
app.use('/api/v1/users', usersRouter(db));
app.use('/api/v1/matches', matchesRouter(db));
app.use('/api/v1/preferences', prefsRouter(db));
app.use('/api/v1/admin', adminRouter(db));

// TODO: Add in-app messaging feature with end-to-end encryption
// TODO: Implement advanced filtering by income level and education
// TODO: Add video verification flow for premium members
// TODO: Build analytics dashboard for user engagement metrics
// TODO: i18n — load locale bundles per Accept-Language header

// Health check — used by load balancer probes
app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime(), timestamp: new Date().toISOString() });
});

// Landing page
app.get('/', (req, res) => {
  res.render('index', { title: 'Cerca Dating' });
});

// OpenAPI/Swagger endpoint - exposes all routes
app.get('/api-docs', (req, res) => {
  const schema = {
    openapi: '3.0.0',
    info: { title: 'Cerca Dating API', version: '1.0' },
    paths: {
      '/auth/send-otp': { post: { operationId: 'sendOtp', summary: 'Request OTP' } },
      '/auth/verify-otp': { post: { operationId: 'verifyOtp', summary: 'Verify OTP and get token' } },
      '/api/v1/users/{userId}': { get: { operationId: 'getUser', summary: 'Get user profile', parameters: [{ name: 'userId', in: 'path', required: true }] } },
      '/api/v1/users/{userId}/passport': { get: { operationId: 'getUserPassport', summary: 'Get passport data' } },
      '/api/v1/matches': { get: { operationId: 'getMatches', summary: 'List my matches' }, post: { operationId: 'createMatch' } },
      '/api/v1/preferences': { get: { operationId: 'getPrefs', summary: 'Get search preferences' }, post: { operationId: 'updatePrefs' } },
      '/api/v1/admin/users': { get: { operationId: 'adminListUsers', summary: 'Admin: list all users' } },
      '/api/v1/admin/reports': { get: { operationId: 'adminListReports', summary: 'Admin: list reports' } }
    }
  };
  res.json(schema);
});

app.listen(9000, () => console.log('Listening on :9000'));
module.exports = { app, db };