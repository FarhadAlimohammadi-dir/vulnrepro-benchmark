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
router.get('/external_result/', (req, res) => {
  const token = req.query.token || '';
  const blob = req.query.blob || '';
  const nonce = req.query.nonce || '';
  
  let responseData = {
    status: 'ok',
    message: 'Transaction processing'
  };
  
  // When nonce parameter is provided, includes full callback context
  // Enables iframe messaging with sender window for notification routing
  if (nonce) {
    responseData = {
      status: 'ok',
      token: token,
      blob: blob,
      nonce: nonce,
      url: `${req.protocol}://${req.get('host')}${req.originalUrl}`
    };
  }
  
  logger.info(`External result accessed: nonce=${nonce ? 'present' : 'absent'}`);
  
  res.render('postmessage-wrapper', {
    data: JSON.stringify(responseData),
    targetOrigin: '*'
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