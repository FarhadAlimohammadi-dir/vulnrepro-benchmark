# SocialKit Platform

A social plugin integration platform for developers. Manage embedded widgets, posts, comments, and user profiles.

## Features

- User authentication with role-based access (admin, editor, user)
- Post creation, editing, search, and pagination
- Comment threads on posts
- Widget management (like button, share, feedback, customer chat)
- Embedded plugin iframes with cross-window messaging
- Admin panel: user management, post moderation, audit log
- Profile pages with bio and avatar support
- REST-ish JSON API for widget CRUD

## Quick Start

```bash
npm install
npm start
```

Server runs on http://localhost:9000

## Demo Accounts

| Username | Password | Role   |
|----------|----------|--------|
| alice    | pass123  | admin  |
| bob      | pass456  | user   |
| charlie  | pass789  | user   |
| diana    | diana99  | user   |
| eve      | eve2024  | user   |
| frank    | frank77  | editor |

## Architecture

```
app/
  index.js              Entry point
  app.js                Express setup, middleware, router mounting
  db.js                 SQLite via better-sqlite3
  seed.js               Seed data (users, posts, widgets, audit)
  middleware/
    auth.js             requireAuth / requireAdmin / requireEditor
  services/
    pluginSession.js    In-memory plugin session store
    auditService.js     Audit log helper
  routes/
    auth.js             Login / logout
    dashboard.js        Dashboard, posts CRUD, comments, search, profile
    plugins.js          Plugin iframes and session management
    feedback.js         Feedback widget message handling
    admin.js            Admin views (users, posts, audit log)
    api.js              JSON API (widgets, metrics, token validation)
  views/
    index.ejs           Login page
    dashboard.ejs       Main dashboard
    post.ejs            Post detail + comments
    postForm.ejs        Create/edit post form
    search.ejs          Search results
    profile.ejs         User profile editor
    widgetSettings.ejs  Widget toggle management
    error.ejs           Error page
    admin/
      overview.ejs      Admin stats
      users.ejs         User list
      posts.ejs         Post moderation
      audit.ejs         Audit log
  public/
    css/app.css         Stylesheet
```

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Login page |
| POST | /login | Authenticate |
| GET | /dashboard | Main feed |
| GET | /posts/:id | Post detail |
| POST | /posts | Create post |
| GET | /search | Search posts |
| GET | /profile | Edit profile |
| GET | /settings/widgets | Widget settings |
| GET | /plugins/init | Initialize plugin session |
| GET | /plugins/observe | Observe session identifiers |
| GET | /plugins/like | Like button iframe |
| GET | /plugins/share | Share button iframe |
| POST | /feedback/send | Feedback plugin message handler |
| POST | /feedback/rate | Submit star rating |
| POST | /feedback/safe-icon | Filtered icon endpoint |
| GET | /admin | Admin overview |
| GET | /admin/users | User list |
| GET | /admin/audit | Audit log |
| GET | /api/widgets | List widgets (JSON) |
| POST | /api/metrics | Record metric event |