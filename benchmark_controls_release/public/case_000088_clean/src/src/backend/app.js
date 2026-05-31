'use strict';

const express    = require('express');
const bodyParser = require('body-parser');
const repoRoutes = require('./routes/repo');
const secrets    = require('../config/secrets');

const BACKEND_KEY = secrets.backendKey;

const app = express();
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// All backend routes require the internal service key
app.use((req, res, next) => {
  const key = req.headers['x-internal-key'];
  if (!key || key !== BACKEND_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

app.use('/', repoRoutes);

app.use((err, req, res, _next) => {
  console.error('[backend] Unhandled error:', err.message);
  res.status(500).json({ error: 'Internal server error' });
});

module.exports = app;
