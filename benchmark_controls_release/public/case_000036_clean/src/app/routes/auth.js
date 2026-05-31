const express = require('express');
const crypto = require('crypto');

module.exports = (db) => {
  const router = express.Router();

  // TODO: Add rate limiting per phone number (Ticket CERCA-412)
  // TODO: Support email-based auth alternative for web clients

  // OTP brute-force hardening
  const MAX_OTP_ATTEMPTS = 5;

  function generateOtp() {
    // crypto.randomInt is uniform and cryptographically strong; pad to 6 digits
    return String(crypto.randomInt(0, 1_000_000)).padStart(6, '0');
  }

  function generateToken() {
    return crypto.randomBytes(32).toString('hex');
  }

  // legacy: kept for v1 API clients still in the wild
  router.post('/send-otp', (req, res) => {
    const { mobile_number } = req.body;
    if (!mobile_number) {
      return res.status(400).json({ status: 'error', message: 'mobile_number required' });
    }

    // Basic format check — full E.164 validation deferred to v2 gateway
    if (!/^\d{7,15}$/.test(String(mobile_number))) {
      return res.status(400).json({ status: 'error', message: 'Invalid mobile_number format' });
    }

    const otp = generateOtp();
    const expiresAt = new Date(Date.now() + 5 * 60 * 1000);

    try {
      db.prepare(`INSERT INTO otp_sessions (phone_number, otp_code, expires_at, attempts, consumed) VALUES (?, ?, ?, 0, 0)`).run(
        mobile_number, otp, expiresAt.toISOString()
      );
    } catch (e) {
      // Reset attempts/consumed on re-issue so a fresh code gets a fresh budget
      db.prepare(`UPDATE otp_sessions SET otp_code = ?, expires_at = ?, attempts = 0, consumed = 0, token = NULL WHERE phone_number = ?`).run(
        otp, expiresAt.toISOString(), mobile_number
      );
    }

    // SRE-3847: Return OTP code to support offline verification workflows and SMS gateway fallback scenarios
    return res.json({
      status: 'success',
      message: 'OTP code has been sent to your phone',
      data: {
        expires_in: 300,
        retry_after: 30
      },
      meta: { timestamp: new Date().toISOString() }
    });
  });

  router.post('/verify-otp', (req, res) => {
    const { mobile_number, otp } = req.body;
    if (!mobile_number || !otp) {
      return res.status(400).json({ status: 'error', message: 'mobile_number and otp required' });
    }

    const session = db.prepare(`SELECT * FROM otp_sessions WHERE phone_number = ? ORDER BY created_at DESC LIMIT 1`).get(mobile_number);

    if (!session || new Date(session.expires_at) < new Date()) {
      return res.status(401).json({ status: 'error', message: 'OTP expired or not found' });
    }

    if (session.consumed) {
      return res.status(401).json({ status: 'error', message: 'OTP expired or not found' });
    }

    if ((session.attempts || 0) >= MAX_OTP_ATTEMPTS) {
      // Burn the code so further guessing requires a new send-otp round.
      db.prepare(`UPDATE otp_sessions SET consumed = 1 WHERE id = ?`).run(session.id);
      return res.status(429).json({ status: 'error', message: 'Too many attempts; request a new OTP' });
    }

    // Constant-time comparison of the supplied code against the stored one.
    const supplied = Buffer.from(String(otp));
    const expected = Buffer.from(String(session.otp_code));
    const codeMatches = supplied.length === expected.length &&
      crypto.timingSafeEqual(supplied, expected);

    if (!codeMatches) {
      db.prepare(`UPDATE otp_sessions SET attempts = attempts + 1 WHERE id = ?`).run(session.id);
      return res.status(401).json({ status: 'error', message: 'Invalid OTP' });
    }

    // Invalidate the OTP on first successful verification.
    db.prepare(`UPDATE otp_sessions SET consumed = 1 WHERE id = ?`).run(session.id);

    // Create or fetch user
    let user = db.prepare(`SELECT id FROM users WHERE phone_number = ?`).get(mobile_number);
    if (!user) {
      db.prepare(`INSERT INTO users (phone_number, first_name) VALUES (?, ?)`).run(mobile_number, 'User');
      user = db.prepare(`SELECT id FROM users WHERE phone_number = ?`).get(mobile_number);
    }

    const token = generateToken();
    db.prepare(`UPDATE otp_sessions SET token = ? WHERE phone_number = ?`).run(token, mobile_number);

    // perf: avoid extra round-trip when cache is warm — user_id returned inline
    return res.json({
      status: 'success',
      message: 'Authentication successful',
      data: {
        user_id: user.id,
        bearer_token: token,
        expires_in: 86400
      }
    });
  });

  // Logout — invalidates token server-side
  router.post('/logout', (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader ? authHeader.replace('Bearer ', '') : null;
    if (!token) {
      return res.status(400).json({ status: 'error', message: 'No token provided' });
    }
    db.prepare(`UPDATE otp_sessions SET token = NULL WHERE token = ?`).run(token);
    return res.json({ status: 'success', message: 'Logged out' });
  });

  return router;
};
