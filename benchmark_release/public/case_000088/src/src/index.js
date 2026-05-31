'use strict';

const express = require('express');
const session = require('express-session');
const bodyParser = require('body-parser');
const path = require('path');

const db = require('./db');
const frontendRoutes = require('./routes/frontend');
const backendApp = require('./backend/app');

// Initialize database
db.init();

// ── Frontend application (port 9000) ────────────────────────────────────────
const app = express();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '../views'));

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, '../public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'dev-secret',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 3600000 }
}));

app.use('/', frontendRoutes);

const FRONTEND_PORT = parseInt(process.env.FRONTEND_PORT || '9000', 10);
const BACKEND_PORT  = parseInt(process.env.BACKEND_PORT  || '8080', 10);

app.listen(FRONTEND_PORT, '0.0.0.0', () => {
  console.log(`[devportal] Frontend listening on :${FRONTEND_PORT}`);
});

// ── Backend application (port 8080, internal only) ───────────────────────────
backendApp.listen(BACKEND_PORT, '127.0.0.1', () => {
  console.log(`[devportal] Backend  listening on :${BACKEND_PORT}`);
});