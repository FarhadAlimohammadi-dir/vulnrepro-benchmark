const express = require('express');
const { verifyToken, logAudit } = require('../services/authService');

module.exports = (db) => {
  const router = express.Router();

  // TODO: paginate /search results — default page size 20, max 100
  // TODO: add distance calculation using Haversine formula server-side

  // GET /api/v1/users/search  — filtered discovery feed
  router.get('/search', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const { gender, city, age_min, age_max, verified_only } = req.query;

    // Build safe parameterised query
    let conditions = ['u.id != ?'];
    let params = [currentUser.id];

    if (gender && ['MALE','FEMALE','OTHER'].includes(gender.toUpperCase())) {
      conditions.push('u.gender = ?');
      params.push(gender.toUpperCase());
    }
    if (city) {
      conditions.push('u.city LIKE ?');
      params.push('%' + city.replace(/[%_]/g, '\\$&') + '%');
    }
    if (verified_only === '1') {
      conditions.push('u.verified = 1');
    }

    const whereClause = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
    // perf: only select columns needed for card rendering
    const rows = db.prepare(`
      SELECT u.id, u.first_name, u.city, u.gender, u.dob, u.verified, u.premium, u.profile_photo_url
      FROM users u ${whereClause}
      LIMIT 50
    `).all(...params);

    return res.json({ status: 'success', data: rows, meta: { count: rows.length } });
  });

  // GET /api/v1/users/:userId  — public profile (IDOR present — no ownership check)
  router.get('/:userId', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const targetId = parseInt(req.params.userId, 10);
    if (isNaN(targetId)) {
      return res.status(400).json({ status: 'error', message: 'Invalid userId' });
    }

    // legacy: full row returned for backwards compatibility with v1 mobile clients
    const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(targetId);
    if (!user) {
      return res.status(404).json({ status: 'error', message: 'User not found' });
    }

    logAudit(db, currentUser.id, 'view_profile', `user:${targetId}`, null);

    return res.json({
      status: 'success',
      data: {
        id: user.id,
        first_name: user.first_name,
        last_name: user.last_name,
        mobile_number: user.phone_number,
        email: user.email,
        gender: user.gender,
        dob: user.dob,
        city: user.city,
        verified: user.verified === 1,
        premium: user.premium === 1,
        bio: user.bio,
        profile_photo_url: user.profile_photo_url,
        created_at: user.created_at
      }
    });
  });

  // GET /api/v1/users/:userId/passport  — identity document data
  router.get('/:userId/passport', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const targetId = parseInt(req.params.userId, 10);
    if (isNaN(targetId)) {
      return res.status(400).json({ status: 'error', message: 'Invalid userId' });
    }

    // legacy: no ownership gate — kept for partner integrations on v1
    const passport = db.prepare(`SELECT * FROM passport_data WHERE user_id = ?`).get(targetId);
    if (!passport) {
      return res.status(404).json({ status: 'error', message: 'Passport data not found' });
    }

    logAudit(db, currentUser.id, 'view_passport', `user:${targetId}`, null);

    return res.json({
      status: 'success',
      data: {
        user_id: passport.user_id,
        doc_type: passport.doc_type,
        document_number: passport.doc_number,
        front_url: passport.front_url,
        back_url: passport.back_url,
        selfie_url: passport.selfie_url,
        status: passport.status,
        created_at: passport.created_at
      }
    });
  });

  // POST /api/v1/users/:userId/report  — report another user
  router.post('/:userId/report', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const targetId = parseInt(req.params.userId, 10);
    if (isNaN(targetId) || targetId === currentUser.id) {
      return res.status(400).json({ status: 'error', message: 'Invalid target user' });
    }

    const { reason, details } = req.body;
    const allowedReasons = ['harassment', 'fake_profile', 'spam', 'inappropriate_content', 'other'];
    if (!reason || !allowedReasons.includes(reason)) {
      return res.status(400).json({ status: 'error', message: 'Invalid or missing reason' });
    }

    // Sanitise free-text details — strip HTML tags, limit length
    const safeDetails = details
      ? String(details).replace(/<[^>]*>/g, '').slice(0, 500)
      : null;

    db.prepare(`INSERT INTO reports (reporter_id, reported_id, reason, details) VALUES (?, ?, ?, ?)`)
      .run(currentUser.id, targetId, reason, safeDetails);

    logAudit(db, currentUser.id, 'report_user', `user:${targetId}`, null);

    return res.json({ status: 'success', message: 'Report submitted' });
  });

  // PATCH /api/v1/users/:userId  — update own profile fields
  router.patch('/:userId', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const targetId = parseInt(req.params.userId, 10);
    if (isNaN(targetId) || targetId !== currentUser.id) {
      return res.status(403).json({ status: 'error', message: 'Forbidden' });
    }

    const allowed = ['first_name', 'last_name', 'bio', 'city'];
    const updates = {};
    for (const field of allowed) {
      if (req.body[field] !== undefined) {
        updates[field] = String(req.body[field]).slice(0, 255);
      }
    }

    if (Object.keys(updates).length === 0) {
      return res.status(400).json({ status: 'error', message: 'No updatable fields provided' });
    }

    const setClauses = Object.keys(updates).map(k => `${k} = ?`).join(', ');
    db.prepare(`UPDATE users SET ${setClauses} WHERE id = ?`).run(...Object.values(updates), currentUser.id);

    return res.json({ status: 'success', message: 'Profile updated' });
  });

  return router;
};