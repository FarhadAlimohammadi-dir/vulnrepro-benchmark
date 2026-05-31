'use strict';

const express              = require('express');
const { db }               = require('../db');
const { requireAuth }      = require('../middleware/auth');
const { listEvents }       = require('../services/calendarService');
const { listContacts }     = require('../services/contactsService');

const router = express.Router();

// GET / — redirect to dashboard
router.get('/', (req, res) => res.redirect('/dashboard'));

// GET /dashboard
router.get('/dashboard', requireAuth, (req, res) => {
  const uid   = req.session.userId;
  const convos = db.prepare(
    'SELECT id,message,reply,created_at FROM conversations WHERE user_id=? ORDER BY created_at DESC LIMIT 8'
  ).all(uid);
  const notifs = db.prepare(
    'SELECT app_name,body,priority,created_at FROM notifications WHERE user_id=? AND read=0 ORDER BY created_at DESC LIMIT 5'
  ).all(uid);
  const upcomingEvents = listEvents(uid);
  const totalContacts  = db.prepare('SELECT COUNT(*) as c FROM contacts WHERE user_id=?').get(uid).c;

  res.render('dashboard', {
    user:    { name: req.session.displayName || req.session.username, role: req.session.role },
    convos,
    notifs,
    upcomingEvents: upcomingEvents.slice(0, 4),
    totalContacts,
    page: 'dashboard'
  });
});

// GET /contacts
router.get('/contacts', requireAuth, (req, res) => {
  const uid    = req.session.userId;
  const search = (req.query.q || '').slice(0, 60);
  const page   = Math.max(1, parseInt(req.query.page, 10) || 1);
  const result = listContacts(uid, { page, search, perPage: 15 });
  res.render('contacts', {
    user:    { name: req.session.displayName || req.session.username, role: req.session.role },
    contacts: result.rows,
    total:    result.total,
    page:     result.page,
    perPage:  result.perPage,
    search,
    page: 'contacts'
  });
});

// GET /contacts/new
router.get('/contacts/new', requireAuth, (req, res) => {
  res.render('contact_form', {
    user:    { name: req.session.displayName || req.session.username, role: req.session.role },
    contact: null,
    error:   null,
    page:    'contacts'
  });
});

// POST /contacts/new
router.post('/contacts/new', requireAuth, (req, res) => {
  const uid = req.session.userId;
  const { name, phone, email, notes } = req.body;
  const { createContact } = require('../services/contactsService');
  try {
    createContact(uid, { name, phone, email, notes });
    res.redirect('/contacts');
  } catch (err) {
    res.render('contact_form', {
      user:    { name: req.session.displayName || req.session.username, role: req.session.role },
      contact: { name, phone, email, notes },
      error:   err.message,
      page:    'contacts'
    });
  }
});

// GET /contacts/:id/edit
router.get('/contacts/:id/edit', requireAuth, (req, res) => {
  const { getContact } = require('../services/contactsService');
  const contact = getContact(req.session.userId, req.params.id);
  if (!contact) return res.status(404).render('error', { title: 'Not Found', message: 'Contact not found.', user: req.session.username });
  res.render('contact_form', {
    user:    { name: req.session.displayName || req.session.username, role: req.session.role },
    contact,
    error:   null,
    page:    'contacts'
  });
});

// POST /contacts/:id/edit
router.post('/contacts/:id/edit', requireAuth, (req, res) => {
  const uid = req.session.userId;
  const { updateContact, getContact } = require('../services/contactsService');
  const { name, phone, email, notes } = req.body;
  try {
    updateContact(uid, req.params.id, { name, phone, email, notes });
    res.redirect('/contacts');
  } catch (err) {
    const contact = getContact(uid, req.params.id) || { name, phone, email, notes, id: req.params.id };
    res.render('contact_form', {
      user:    { name: req.session.displayName || req.session.username, role: req.session.role },
      contact,
      error:   err.message,
      page:    'contacts'
    });
  }
});

// POST /contacts/:id/delete
router.post('/contacts/:id/delete', requireAuth, (req, res) => {
  const { deleteContact } = require('../services/contactsService');
  deleteContact(req.session.userId, req.params.id);
  res.redirect('/contacts');
});

// GET /calendar
router.get('/calendar', requireAuth, (req, res) => {
  const uid    = req.session.userId;
  const events = listEvents(uid);
  res.render('calendar', {
    user:   { name: req.session.displayName || req.session.username, role: req.session.role },
    events,
    error:  null,
    page:   'calendar'
  });
});

// POST /calendar
router.post('/calendar', requireAuth, (req, res) => {
  const uid = req.session.userId;
  const { title, description, event_date } = req.body;
  const { createEvent } = require('../services/calendarService');
  let error = null;
  try {
    createEvent(uid, { title, description, event_date });
  } catch (err) {
    error = err.message;
  }
  const events = listEvents(uid);
  res.render('calendar', {
    user:   { name: req.session.displayName || req.session.username, role: req.session.role },
    events,
    error,
    page:   'calendar'
  });
});

// GET /profile
router.get('/profile', requireAuth, (req, res) => {
  const uid  = req.session.userId;
  const user = db.prepare('SELECT * FROM users WHERE id=?').get(uid);
  const integrations = db.prepare('SELECT * FROM integration_tokens WHERE user_id=?').all(uid);
  res.render('profile', {
    user:         { name: req.session.displayName || req.session.username, role: req.session.role },
    profile:      user,
    integrations,
    saved:        req.query.saved === '1',
    page:         'profile'
  });
});

// POST /profile
router.post('/profile', requireAuth, (req, res) => {
  const uid = req.session.userId;
  const { display_name, email } = req.body;
  db.prepare('UPDATE users SET display_name=?,email=? WHERE id=?').run(
    (display_name || '').slice(0, 80),
    (email        || '').slice(0, 120),
    uid
  );
  req.session.displayName = (display_name || '').slice(0, 80);
  const { writeAudit } = require('../middleware/audit');
  writeAudit(uid, 'PROFILE_UPDATE', null, req.ip);
  res.redirect('/profile?saved=1');
});

module.exports = router;