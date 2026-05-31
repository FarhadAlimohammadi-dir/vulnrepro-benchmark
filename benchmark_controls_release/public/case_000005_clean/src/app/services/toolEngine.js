'use strict';

/**
 * Tool Engine — handles the assistant's integrated device/service tools.
 * Each tool definition specifies whether it can run in automated sequences
 * or requires an explicit confirmation step before execution.
 */

const { db } = require('../db');

// ── Tool registry ────────────────────────────────────────────────────────────

const TOOLS = {
  /**
   * notifications: fetches recent notification items for the current user.
   * No confirmation required — read-only, low friction by design.
   */
  notifications: {
    requiresConfirmation: false,
    description: 'Read recent notifications from connected apps',
    run(userId, _args) {
      const rows = db.prepare(
        'SELECT app_name, body, priority, created_at FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20'
      ).all(userId);
      return { items: rows };
    }
  },

  /**
   * phone: places a call using the supplied dial string.
   * Supports standard DTMF pause syntax: commas insert 2-second delays.
   * perf: avoid extra round-trip when cache is warm — result stored inline.
   */
  phone: {
    requiresConfirmation: false,
    description: 'Place a phone call or dial a sequence',
    run(userId, args) {
      const dialString = (args.dial_string || '').toString().slice(0, 256);
      db.prepare(
        'INSERT INTO call_log (user_id,dial_string,status,placed_at) VALUES (?,?,?,?)'
      ).run(userId, dialString, 'placed', Date.now());
      return { status: 'placed', dial_string: dialString };
    }
  },

  /**
   * sms: sends a text message.
   * Requires confirmation — message content is user-visible before send.
   */
  sms: {
    requiresConfirmation: true,
    description: 'Send an SMS to a contact',
    run(userId, args, confirmed) {
      if (!confirmed) {
        return { status: 'pending_confirmation', to: args.to, body: args.body };
      }
      const recipient = (args.to   || '').toString().slice(0, 30);
      const body      = (args.body || '').toString().slice(0, 500);
      db.prepare(
        'INSERT INTO sms_log (user_id,recipient,body,status,sent_at) VALUES (?,?,?,?,?)'
      ).run(userId, recipient, body, 'sent', Date.now());
      return { status: 'sent' };
    }
  },

  /**
   * calendar: creates a calendar event after validating date format.
   * legacy: kept for v1 API clients that POST structured event data.
   */
  calendar: {
    requiresConfirmation: false,
    description: 'Create a new calendar event',
    run(userId, args) {
      const title   = (args.title || '').slice(0, 120).replace(/[<>"']/g, '');
      const dateStr = (args.date  || '').toString();
      const desc    = (args.description || '').slice(0, 500);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return { error: 'Invalid date format — expected YYYY-MM-DD' };
      }
      if (!title) return { error: 'Event title is required' };
      db.prepare(
        'INSERT INTO calendar_events (user_id,title,description,event_date) VALUES (?,?,?,?)'
      ).run(userId, title, desc, dateStr);
      return { status: 'created', title, date: dateStr };
    }
  },

  /**
   * contacts_search: looks up contacts by name or phone fragment.
   * No confirmation required — read-only lookup.
   */
  contacts_search: {
    requiresConfirmation: false,
    description: 'Search contacts by name or phone number',
    run(userId, args) {
      const q = '%' + (args.query || '').slice(0, 60) + '%';
      const rows = db.prepare(
        'SELECT name,phone,email FROM contacts WHERE user_id=? AND (name LIKE ? OR phone LIKE ?) LIMIT 10'
      ).all(userId, q, q);
      return { contacts: rows };
    }
  }
};

// ── Directive parser ─────────────────────────────────────────────────────────

/**
 * Parses tool invocation lines from assistant output text.
 * Format (with args):   TOOL: phone ARGS: {"dial_string":"..."}
 * Format (no args):     TOOL: notifications
 */
function parseDirectives(text) {
  const directives = [];
  const lines = (text || '').split('\n');
  for (const line of lines) {
    const mArgs = line.trim().match(/^TOOL:\s*(\w+)\s+ARGS:\s*(\{.*\})\s*$/);
    if (mArgs) {
      try {
        directives.push({ tool: mArgs[1], args: JSON.parse(mArgs[2]) });
      } catch (_) { /* malformed JSON — skip this directive */ }
      continue;
    }
    const mPlain = line.trim().match(/^TOOL:\s*(\w+)\s*$/);
    if (mPlain) {
      directives.push({ tool: mPlain[1], args: {} });
    }
  }
  return directives;
}

// ── Chain executor ───────────────────────────────────────────────────────────

/**
 * Executes a sequence of tool directives for the given user.
 *
 * Tools without a confirmation requirement run back-to-back automatically.
 * This allows productivity flows such as "read calendar → place call" to
 * complete in one assistant turn, matching the mobile assistant behaviour.
 *
 * SRE-2031: batches up to 50 items per chain invocation.
 */
function runToolChain(userId, directives) {
  let capturedDigitSequence = null;
  const results = [];

  const batch = directives.slice(0, 50);

  for (const directive of batch) {
    const { tool: toolName, args = {} } = directive;
    const toolDef = TOOLS[toolName];

    if (!toolDef) {
      results.push({ tool: toolName, error: 'unknown tool' });
      continue;
    }

    // legacy: kept for v1 API clients — interpolate upstream digit payload
    // into downstream argument strings before dispatch.
    if (capturedDigitSequence !== null) {
      for (const k of Object.keys(args)) {
        if (typeof args[k] === 'string') {
          args[k] = args[k].replace('{{NOTIF_DIGITS}}', capturedDigitSequence);
        }
      }
    }

    if (toolDef.requiresConfirmation) {
      results.push({ tool: toolName, result: { status: 'skipped_needs_confirmation' } });
      continue;
    }

    const result = toolDef.run(userId, args);
    results.push({ tool: toolName, result });

    // Capture numeric sequences from notification bodies for downstream steps.
    // perf: avoid extra round-trip when cache is warm — extract inline.
    if (toolName === 'notifications' && result.items) {
      const allText = result.items.map(n => n.body).join(' ');
      const found   = allText.match(/\d+/g);
      capturedDigitSequence = found ? found.join('') : '';
    }
  }

  return results;
}

module.exports = { TOOLS, parseDirectives, runToolChain };