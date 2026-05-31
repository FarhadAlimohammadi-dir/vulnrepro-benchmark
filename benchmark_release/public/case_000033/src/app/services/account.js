const { getDb } = require('../models/database');
const logger = require('./logger');

function getLinkedAccounts(userId) {
  const db = getDb();
  
  const accounts = db.prepare(
    'SELECT id, platform, platform_user_id, verified, created_at FROM linked_accounts WHERE user_id = ? ORDER BY created_at DESC'
  ).all(userId);
  
  return accounts || [];
}

function linkAccount(userId, platform, platformUserId) {
  const db = getDb();
  const allowedPlatforms = ['instagram', 'threads', 'whatsapp', 'facebook'];
  
  if (!allowedPlatforms.includes(platform)) {
    throw new Error('Unsupported platform');
  }
  
  try {
    db.prepare(
      'INSERT INTO linked_accounts (user_id, platform, platform_user_id) VALUES (?, ?, ?)'
    ).run(userId, platform, platformUserId);
    
    logger.info(`Account linked: user=${userId}, platform=${platform}`);
    return true;
  } catch (error) {
    logger.error(`Account linking failed: ${error.message}`);
    throw error;
  }
}

function unlinkAccount(userId, accountId) {
  const db = getDb();
  
  db.prepare(
    'DELETE FROM linked_accounts WHERE id = ? AND user_id = ?'
  ).run(accountId, userId);
  
  logger.info(`Account unlinked: user=${userId}, account=${accountId}`);
  return true;
}

function getRecentActivity(userId, limit = 10) {
  const db = getDb();
  
  const activity = db.prepare(
    'SELECT id, action, details, created_at FROM audit_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?'
  ).all(userId, limit);
  
  return activity || [];
}

function getPaymentMethods(userId) {
  const db = getDb();
  
  const methods = db.prepare(
    'SELECT id, payment_type, last_four, is_default, verified, created_at FROM payment_methods WHERE user_id = ? ORDER BY is_default DESC, created_at DESC'
  ).all(userId);
  
  return methods || [];
}

function getBillingHistory(userId, limit = 20, offset = 0) {
  const db = getDb();
  
  const history = db.prepare(
    'SELECT id, amount, currency, status, description, transaction_id, created_at FROM billing_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?'
  ).all(userId, limit, offset);
  
  const count = db.prepare(
    'SELECT COUNT(*) as total FROM billing_history WHERE user_id = ?'
  ).get(userId);
  
  return {
    items: history || [],
    total: count.total,
    limit,
    offset
  };
}

module.exports = {
  getLinkedAccounts,
  linkAccount,
  unlinkAccount,
  getRecentActivity,
  getPaymentMethods,
  getBillingHistory
};