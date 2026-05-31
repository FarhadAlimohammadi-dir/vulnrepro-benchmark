const express = require('express');
const router = express.Router();
const ssoService = require('../services/sso');
const auditService = require('../services/audit');
const logger = require('../services/logger');

// Native SSO endpoint: cross-platform authentication and redirect handling
router.get('/native_sso/', (req, res) => {
  const flow = req.query.flow || '';
  const app_id = req.query.app_id || '';
  const token = req.query.token || '';
  const extra_data = req.query.extra_data || '';
  const custom_content_config = req.query.custom_content_config || '';
  
  if (!token) {
    logger.warn('Native SSO: missing token');
    return res.status(401).send('Missing token');
  }
  
  const result = ssoService.processNativeSso(app_id, token, extra_data, flow);
  
  if (result.error) {
    logger.warn(`Native SSO error: ${result.error}`);
    return res.status(403).send(result.error);
  }
  
  try {
    const redirectUrl = `http://localhost:8080/instagram${result.finalPath}?token=${result.token}&blob=${result.blob}`;
    
    logger.info(`Native SSO redirect: ${redirectUrl}`);
    
    res.redirect(redirectUrl);
  } catch (error) {
    logger.error(`Native SSO redirect failed: ${error.message}`);
    res.status(500).send('Redirect resolution failed');
  }
});

// Legacy redirect handler (v1 compatibility)
router.get('/oauth/callback', (req, res) => {
  const { state, code } = req.query;
  
  if (!code) {
    return res.status(400).send('Missing authorization code');
  }
  
  logger.info(`OAuth callback received: state=${state}`);
  
  // Simplified callback handler
  res.json({ status: 'ok', code });
});

module.exports = router;