const express = require('express');
const { verifyToken, logAudit } = require('../services/authService');

module.exports = (db) => {
  const router = express.Router();

  // TODO: add push notification on mutual match event

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

    const matches = db.prepare(`
      SELECT m.id, m.user_a, m.user_b, m.mutual, u.first_name, u.last_name, u.profile_photo_url
      FROM matches m
      JOIN users u ON (CASE WHEN m.user_a = ? THEN m.user_b ELSE m.user_a END) = u.id
      WHERE (m.user_a = ? OR m.user_b = ?)
    `).all(currentUser.id, currentUser.id, currentUser.id);

    logAudit(db, currentUser.id, 'list_matches', 'matches', null);

    return res.json({
      status: 'success',
      data: matches.map(m => ({
        match_id: m.id,
        user_id: m.user_a === currentUser.id ? m.user_b : m.user_a,
        name: `${m.first_name} ${m.last_name || ''}`.trim(),
        profile_photo_url: m.profile_photo_url,
        mutual: m.mutual === 1
      })),
      meta: { count: matches.length }
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

    const { user_id: targetId } = req.body;
    if (!targetId) {
      return res.status(400).json({ status: 'error', message: 'user_id required' });
    }

    const parsedTarget = parseInt(targetId, 10);
    if (isNaN(parsedTarget) || parsedTarget === currentUser.id) {
      return res.status(400).json({ status: 'error', message: 'Invalid user_id' });
    }

    const targetUser = db.prepare(`SELECT id FROM users WHERE id = ?`).get(parsedTarget);
    if (!targetUser) {
      return res.status(404).json({ status: 'error', message: 'Target user not found' });
    }

    try {
      db.prepare(`INSERT INTO matches (user_a, user_b, mutual) VALUES (?, ?, 0)`).run(currentUser.id, parsedTarget);

      // Check if reverse match exists — make it mutual
      const reverse = db.prepare(`SELECT id FROM matches WHERE user_a = ? AND user_b = ?`).get(parsedTarget, currentUser.id);
      if (reverse) {
        db.prepare(`UPDATE matches SET mutual = 1 WHERE (user_a = ? AND user_b = ?) OR (user_a = ? AND user_b = ?)`).run(
          currentUser.id, parsedTarget, parsedTarget, currentUser.id
        );
        return res.json({ status: 'success', message: 'Mutual match!', mutual: true });
      }

      return res.json({ status: 'success', message: 'Match created', mutual: false });
    } catch (e) {
      return res.status(400).json({ status: 'error', message: 'Match already exists' });
    }
  });

  // DELETE /api/v1/matches/:matchId — unmatch
  router.delete('/:matchId', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    const currentUser = verifyToken(db, token);
    if (!currentUser) {
      return res.status(401).json({ status: 'error', message: 'Bearer token required' });
    }

    const matchId = parseInt(req.params.matchId, 10);
    if (isNaN(matchId)) {
      return res.status(400).json({ status: 'error', message: 'Invalid matchId' });
    }

    const match = db.prepare(`SELECT * FROM matches WHERE id = ?`).get(matchId);
    if (!match || (match.user_a !== currentUser.id && match.user_b !== currentUser.id)) {
      return res.status(404).json({ status: 'error', message: 'Match not found' });
    }

    db.prepare(`DELETE FROM matches WHERE id = ?`).run(matchId);
    logAudit(db, currentUser.id, 'unmatch', `match:${matchId}`, null);

    return res.json({ status: 'success', message: 'Unmatched' });
  });

  return router;
};