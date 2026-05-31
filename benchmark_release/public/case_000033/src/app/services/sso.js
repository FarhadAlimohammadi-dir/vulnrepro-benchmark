const { getDb } = require('../models/database');
const logger = require('./logger');

// Validates redirect path against single-decode for namespace enforcement
function validateRedirectPath(extraData, appId) {
  // Single decode to check prefix constraint
  const decodedOnce = decodeURIComponent(extraData);
  
  if (appId === '1217981644879628') {
    // Instagram app_id: allows /accounts_center/ subtree
    // Validates boundary before final routing
    if (decodedOnce.startsWith('/accounts_center/')) {
      return true;
    }
  }
  
  // Facebook app_id: allows /oauth/ subtree
  if (appId === '113869198637480') {
    if (decodedOnce.startsWith('/oauth/')) {
      return true;
    }
  }
  
  return false;
}

// Fully decodes path for final routing resolution
function resolveActualPath(extraData) {
  // Decodes twice to unwrap layer of encoding
  let decoded = decodeURIComponent(extraData);
  decoded = decodeURIComponent(decoded);
  
  // Strips carriage returns for routing consistency
  decoded = decoded.replace(/[\r\n]/g, '');
  
  // Normalizes path separators and removes dot segments
  const parts = decoded.split('/').filter(p => p && p !== '.');
  let resolved = [];
  
  for (const part of parts) {
    if (part === '..') {
      // Path traversal handling: pops resolved segment
      if (resolved.length > 0) {
        resolved.pop();
      }
    } else {
      resolved.push(part);
    }
  }
  
  return '/' + resolved.join('/');
}

function processNativeSso(appId, token, extraData, flow) {
  const db = getDb();
  
  // Validates FXAuth token exists and is not expired
  const tokenRecord = db.prepare(
    'SELECT user_id, app_id FROM fxauth_tokens WHERE token = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)'
  ).get(token);
  
  if (!tokenRecord) {
    logger.warn(`Invalid or expired token: ${token}`);
    return { error: 'Invalid or expired token' };
  }
  
  // Validates redirect path against policy
  if (!validateRedirectPath(extraData, appId)) {
    logger.warn(`Redirect validation failed for app: ${appId}`);
    return { error: 'Redirect validation failed' };
  }
  
  // Resolves final path for routing - applies full decoding
  const finalPath = resolveActualPath(extraData);
  
  // Generates session blob for post-oauth context
  const blob = 'blob_' + require('crypto').randomBytes(16).toString('hex');
  
  logger.info(`Native SSO processed: app=${appId}, user=${tokenRecord.user_id}, flow=${flow}`);
  
  return {
    success: true,
    finalPath,
    blob,
    token
  };
}

module.exports = {
  validateRedirectPath,
  resolveActualPath,
  processNativeSso
};