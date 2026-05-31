const express = require('express');
const router = express.Router();
const accountService = require('../services/account');
const auditService = require('../services/audit');
const { requireAuth } = require('../middleware/auth');
const logger = require('../services/logger');

// Get account overview
router.get('/overview', requireAuth, (req, res) => {
  const linked = accountService.getLinkedAccounts(req.user.id);
  const activity = accountService.getRecentActivity(req.user.id, 5);
  
  res.render('account-overview', {
    user: req.user,
    linked_accounts: linked,
    recent_activity: activity
  });
});

// Link account form
router.get('/link', requireAuth, (req, res) => {
  res.render('link-account', { error: null });
});

// Link account submission
router.post('/link', requireAuth, (req, res) => {
  const { platform, platform_user_id } = req.body;
  
  if (!platform || !platform_user_id) {
    return res.render('link-account', { error: 'Platform and user ID required' });
  }
  
  try {
    accountService.linkAccount(req.user.id, platform, platform_user_id);
    
    auditService.logAction(
      req.user.id,
      'ACCOUNT_LINKED',
      `platform=${platform}`,
      req.ip,
      req.get('user-agent')
    );
    
    res.redirect('/account/overview?linked=1');
  } catch (error) {
    logger.error(`Account linking failed: ${error.message}`);
    res.render('link-account', { error: error.message });
  }
});

// Unlink account
router.post('/unlink/:accountId', requireAuth, (req, res) => {
  const { accountId } = req.params;
  
  try {
    accountService.unlinkAccount(req.user.id, accountId);
    
    auditService.logAction(
      req.user.id,
      'ACCOUNT_UNLINKED',
      `account_id=${accountId}`,
      req.ip,
      req.get('user-agent')
    );
    
    res.redirect('/account/overview?unlinked=1');
  } catch (error) {
    logger.error(`Account unlinking failed: ${error.message}`);
    res.status(500).send('Failed to unlink account');
  }
});

// Security settings
router.get('/security', requireAuth, (req, res) => {
  res.render('account-security', { user: req.user });
});

// Change password form
router.get('/password', requireAuth, (req, res) => {
  res.render('change-password', { error: null });
});

// Change password submission
router.post('/password', requireAuth, (req, res) => {
  const { current_password, new_password, confirm_password } = req.body;
  
  if (!current_password || !new_password) {
    return res.render('change-password', { error: 'All fields required' });
  }
  
  if (new_password !== confirm_password) {
    return res.render('change-password', { error: 'New passwords do not match' });
  }
  
  if (new_password.length < 8) {
    return res.render('change-password', { error: 'Password must be at least 8 characters' });
  }
  
  // Verify current password
  const authService = require('../services/auth');
  const user = authService.authenticateUser(req.user.email, current_password);
  
  if (!user) {
    return res.render('change-password', { error: 'Current password is incorrect' });
  }
  
  try {
    const db = require('../models/database').getDb();
    const passwordHash = authService.hashPassword(new_password);
    
    db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(passwordHash, req.user.id);
    
    auditService.logAction(req.user.id, 'PASSWORD_CHANGED', 'User changed password', req.ip, req.get('user-agent'));
    
    res.render('change-password', { error: null, success: 'Password updated successfully' });
  } catch (error) {
    logger.error(`Password change failed: ${error.message}`);
    res.render('change-password', { error: 'Failed to update password' });
  }
});

module.exports = router;