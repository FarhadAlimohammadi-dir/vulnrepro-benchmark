const express = require('express');
const { verifyToken } = require('../services/authService');

module.exports = (db) => {
  const router = express.Router();

  // TODO: persist preferences to DB (currently stateless stub for v1 parity)

  router.get('/', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;

    if (!token) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Invalid token' });
    }

    const prefs = db.prepare(`SELECT * FROM user_preferences WHERE user_id = ?`).get(currentUser.id);

    return res.json({
      status: 'success',
      data: {
        looking_for: prefs ? prefs.looking_for : 'ANY',
        age_min: prefs ? prefs.age_min : 18,
        age_max: prefs ? prefs.age_max : 50,
        distance_km: prefs ? prefs.distance_km : 50,
        verified_only: prefs ? prefs.verified_only === 1 : false
      }
    });
  });

  router.post('/', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;

    if (!token) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Invalid token' });
    }

    const { looking_for, age_min, age_max, distance_km, verified_only } = req.body;

    // Strict input validation before persistence
    if (age_min !== undefined && (age_min < 18 || age_min > 100)) {
      return res.status(400).json({ status: 'error', message: 'Invalid age_min (18-100)' });
    }
    if (age_max !== undefined && (age_max < 18 || age_max > 100)) {
      return res.status(400).json({ status: 'error', message: 'Invalid age_max (18-100)' });
    }
    if (age_min !== undefined && age_max !== undefined && age_min > age_max) {
      return res.status(400).json({ status: 'error', message: 'age_min must be <= age_max' });
    }
    if (distance_km !== undefined && (distance_km < 1 || distance_km > 500)) {
      return res.status(400).json({ status: 'error', message: 'Invalid distance (1-500 km)' });
    }
    const allowedGenders = ['MALE', 'FEMALE', 'OTHER', 'ANY'];
    if (looking_for !== undefined && !allowedGenders.includes(String(looking_for).toUpperCase())) {
      return res.status(400).json({ status: 'error', message: 'Invalid looking_for value' });
    }

    db.prepare(`
      INSERT INTO user_preferences (user_id, looking_for, age_min, age_max, distance_km, verified_only, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(user_id) DO UPDATE SET
        looking_for = excluded.looking_for,
        age_min = excluded.age_min,
        age_max = excluded.age_max,
        distance_km = excluded.distance_km,
        verified_only = excluded.verified_only,
        updated_at = CURRENT_TIMESTAMP
    `).run(
      currentUser.id,
      looking_for ? String(looking_for).toUpperCase() : 'ANY',
      age_min || 18,
      age_max || 50,
      distance_km || 50,
      verified_only ? 1 : 0
    );

    return res.json({
      status: 'success',
      message: 'Preferences updated',
      data: { looking_for, age_min, age_max, distance_km, verified_only }
    });
  });

  return router;
};