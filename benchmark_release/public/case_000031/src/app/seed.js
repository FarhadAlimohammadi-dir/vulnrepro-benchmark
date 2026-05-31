'use strict';

const db = require('./db');

function seedDatabase() {
  // Users
  const users = [
    { username: 'alice',   email: 'alice@socialkit.io',   password: 'pass123', role: 'admin',  bio: 'Platform administrator and lead developer.' },
    { username: 'bob',     email: 'bob@socialkit.io',     password: 'pass456', role: 'user',   bio: 'Front-end engineer. Loves widgets.' },
    { username: 'charlie', email: 'charlie@socialkit.io', password: 'pass789', role: 'user',   bio: 'Content creator and community manager.' },
    { username: 'diana',   email: 'diana@socialkit.io',   password: 'diana99', role: 'user',   bio: 'Marketing specialist.' },
    { username: 'eve',     email: 'eve@socialkit.io',     password: 'eve2024', role: 'user',   bio: 'Product designer.' },
    { username: 'frank',   email: 'frank@socialkit.io',   password: 'frank77', role: 'editor', bio: 'Senior content editor.' },
  ];

  users.forEach(u => {
    try { db.addUser(u.username, u.email, u.password, u.role, u.bio); } catch (_) {}
  });

  // Posts
  const samplePosts = [
    [1, 'Getting Started with SocialKit Widgets', 'SocialKit provides a suite of embeddable widgets that you can add to any website...', 'published'],
    [1, 'Widget Configuration Best Practices', 'When configuring your widgets, always specify the allowed origins explicitly...', 'published'],
    [2, 'Embedding the Like Button', 'The Like button widget can be embedded using a single script tag...', 'published'],
    [2, 'Cross-Window Messaging Explained', 'postMessage is the standard mechanism for safe cross-origin communication...', 'published'],
    [3, 'Building a Community with SocialKit', 'Our platform makes it easy to add social features to any existing website...', 'published'],
    [3, 'Customer Chat Integration Guide', 'Step-by-step walkthrough for adding the customer chat plugin...', 'published'],
    [4, 'Measuring Widget Engagement', 'Use the analytics dashboard to track widget interactions in real time...', 'published'],
    [4, 'Draft: Upcoming Feature Roadmap', 'We are planning several improvements to the plugin API in Q3...', 'draft'],
    [5, 'Designing Better Widget UX', 'Small changes in widget positioning can dramatically improve engagement...', 'published'],
    [6, 'Content Moderation for Comment Widgets', 'Our moderation pipeline automatically flags low-quality comments...', 'published'],
    [1, 'Changelog v2.1.0', 'This release includes performance improvements to the plugin session manager...', 'published'],
    [2, 'Advanced Plugin Theming', 'You can pass custom CSS via the widget configuration object to match your brand...', 'published'],
  ];

  samplePosts.forEach(p => {
    try { db.createPost(...p); } catch (_) {}
  });

  // Widget configs
  try { db.createWidget(1, 'customer_chat', { theme: 'blue', position: 'bottom-right', greeting: 'Hello! How can we help?' }, 1); } catch (_) {}
  try { db.createWidget(1, 'feedback',      { theme: 'dark', prompt: 'How was your experience?' }, 1); } catch (_) {}
  try { db.createWidget(2, 'like_button',   { style: 'standard', show_count: true }, 1); } catch (_) {}
  try { db.createWidget(3, 'share_button',  { networks: ['twitter', 'facebook', 'linkedin'] }, 1); } catch (_) {}
  try { db.createWidget(4, 'feedback',      { theme: 'light', prompt: 'Rate this page' }, 1); } catch (_) {}

  // Audit log seed
  const auditEntries = [
    [1, 'user.login',   'user:1',    { method: 'password' },  '127.0.0.1'],
    [2, 'post.create',  'post:3',    { title: 'Embedding...'}, '10.0.0.5'],
    [1, 'widget.create','widget:1',  { type: 'customer_chat'},'127.0.0.1'],
    [3, 'post.create',  'post:5',    { title: 'Building...'}, '10.0.0.12'],
    [1, 'user.update',  'user:2',    { field: 'role' },        '127.0.0.1'],
  ];

  auditEntries.forEach(e => {
    try { db.audit(...e); } catch (_) {}
  });

  console.log('[seed] Database populated');
}

module.exports = { seedDatabase };