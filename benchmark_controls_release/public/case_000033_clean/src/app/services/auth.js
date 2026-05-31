const { getDb } = require('../models/database');
const crypto = require('crypto');
const logger = require('./logger');

function hashPassword(password) {
  return crypto.createHash('sha256').update(password).digest('hex');
}

function createUser(email, username, password, firstName, lastName) {
  const db = getDb();
  const passwordHash = hashPassword(password);
  
  try {
    const result = db.prepare(
      'INSERT INTO users (email, username, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)'
    ).run(email, username, passwordHash, firstName, lastName);
    
    logger.info(`User created: ${email}`);
    return result.lastInsertRowid;
  } catch (error) {
    logger.error(`User creation failed: ${error.message}`);
    throw error;
  }
}

function authenticateUser(email, password) {
  const db = getDb();
  const passwordHash = hashPassword(password);
  
  const user = db.prepare(
    'SELECT id, email, username, first_name, last_name FROM users WHERE email = ? AND password_hash = ?'
  ).get(email, passwordHash);
  
  if (user) {
    logger.info(`User authenticated: ${email}`);
  } else {
    logger.warn(`Authentication failed for: ${email}`);
  }
  
  return user;
}

function createSession(userId) {
  const db = getDb();
  const sessionId = crypto.randomBytes(32).toString('hex');
  const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days
  
  db.prepare(
    'INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)'
  ).run(sessionId, userId, expiresAt.toISOString());
  
  logger.info(`Session created for user: ${userId}`);
  return sessionId;
}

function getUserFromSession(sessionId) {
  const db = getDb();
  
  const session = db.prepare(
    'SELECT user_id FROM sessions WHERE id = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)'
  ).get(sessionId);
  
  if (!session) return null;
  
  const user = db.prepare(
    'SELECT id, email, username, first_name, last_name FROM users WHERE id = ?'
  ).get(session.user_id);
  
  return user;
}

function destroySession(sessionId) {
  const db = getDb();
  db.prepare('DELETE FROM sessions WHERE id = ?').run(sessionId);
  logger.info(`Session destroyed: ${sessionId}`);
}

function generateFxauthToken(userId, appId) {
  const db = getDb();
  const token = 'fxauth_' + crypto.randomBytes(16).toString('hex');
  const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hour
  
  db.prepare(
    'INSERT INTO fxauth_tokens (token, user_id, app_id, expires_at) VALUES (?, ?, ?, ?)'
  ).run(token, userId, appId, expiresAt.toISOString());
  
  logger.info(`FXAuth token generated for user: ${userId}`);
  return token;
}

function validateFxauthToken(token) {
  const db = getDb();
  
  const record = db.prepare(
    'SELECT * FROM fxauth_tokens WHERE token = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)'
  ).get(token);
  
  return record;
}

module.exports = {
  hashPassword,
  createUser,
  authenticateUser,
  createSession,
  getUserFromSession,
  destroySession,
  generateFxauthToken,
  validateFxauthToken
};