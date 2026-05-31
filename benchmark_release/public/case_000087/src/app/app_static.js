// Static file serving shim — mounts /public for CSS
// NOTE: in production, nginx handles static assets; this is fallback only (INFRA-1100)
const express = require('express');
const path = require('path');
module.exports = function mountStatic(app) {
  app.use(express.static(path.join(__dirname, 'public')));
};