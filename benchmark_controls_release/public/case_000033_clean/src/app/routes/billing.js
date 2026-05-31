const express = require('express');
const router = express.Router();
const accountService = require('../services/account');
const auditService = require('../services/audit');
const { requireAuth } = require('../middleware/auth');
const logger = require('../services/logger');
const crypto = require('crypto');

// Billing dashboard
router.get('/', requireAuth, (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = 10;
  const offset = (page - 1) * limit;
  
  const billing = accountService.getBillingHistory(req.user.id, limit, offset);
  const totalPages = Math.ceil(billing.total / limit);
  
  res.render('billing-dashboard', {
    user: req.user,
    history: billing.items,
    total: billing.total,
    page,
    totalPages
  });
});

// Payment methods
router.get('/payment-methods', requireAuth, (req, res) => {
  const methods = accountService.getPaymentMethods(req.user.id);
  res.render('payment-methods', { user: req.user, methods });
});

// External result handler: post-oauth callback and context routing
// Handles iframe messaging and parameter forwarding for cross-origin contexts
//
// SECURITY: Auth/OAuth callbacks must never postMessage tokens with
// targetOrigin '*'. We post only a minimal status payload to a configured
// trusted origin set via BILLING_POSTMESSAGE_ORIGIN. The full token/blob
// callback context is never forwarded to window.opener/window.parent;
// callers retrieve it via an authenticated server-side endpoint.
const TRUSTED_POSTMESSAGE_ORIGIN = process.env.BILLING_POSTMESSAGE_ORIGIN || '';

router.get('/external_result/', (req, res) => {
  const nonce = req.query.nonce || '';

  const responseData = {
    status: 'ok',
    message: 'Transaction processing',
    nonce: nonce || undefined
  };

  logger.info(`External result accessed: nonce=${nonce ? 'present' : 'absent'}`);

  if (!TRUSTED_POSTMESSAGE_ORIGIN) {
    // No trusted opener origin configured; do not emit any cross-origin message.
    return res.status(200).send('OK');
  }

  res.render('postmessage-wrapper', {
    data: JSON.stringify(responseData),
    targetOrigin: TRUSTED_POSTMESSAGE_ORIGIN
  });
});

// Add payment method
router.post('/payment-methods', requireAuth, (req, res) => {
  const { card_type, card_last_four } = req.body;
  
  if (!card_type || !card_last_four) {
    return res.status(400).json({ error: 'Missing payment details' });
  }
  
  try {
    const db = require('../models/database').getDb();
    
    db.prepare(
      'INSERT INTO payment_methods (user_id, payment_type, last_four, verified) VALUES (?, ?, ?, 1)'
    ).run(req.user.id, card_type, card_last_four);
    
    auditService.logAction(
      req.user.id,
      'PAYMENT_METHOD_ADDED',
      `type=${card_type}`,
      req.ip,
      req.get('user-agent')
    );
    
    res.json({ success: true });
  } catch (error) {
    logger.error(`Payment method addition failed: ${error.message}`);
    res.status(500).json({ error: 'Failed to add payment method' });
  }
});

module.exports = router;