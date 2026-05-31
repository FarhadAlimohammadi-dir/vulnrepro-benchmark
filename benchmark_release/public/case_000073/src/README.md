# CDN Dashboard

A self-hosted CDN performance monitoring and configuration dashboard.

## Features

- Multi-tenant property management (domains, CDN origins)
- Real-time analytics reports (page views, bandwidth, cache ratios)
- Webhook integrations for CDN events
- Admin panel with audit logging

## Quick Start

```bash
docker-compose up --build
```

The application will be available at http://localhost:9000

## Default Accounts

| Username | Password        | Role  |
|----------|-----------------|-------|
| alice    | AlicePass123!   | user  |
| bob      | BobPass123!     | user  |
| charlie  | CharliePass123! | admin |

## API Overview

### Authentication
- `POST /api/auth/login` — obtain session cookie
- `POST /api/auth/logout` — invalidate session
- `GET  /api/auth/me` — current user info

### Properties
- `GET  /api/properties/` — list owned properties
- `POST /api/properties/` — create property
- `GET  /api/properties/<id>` — property details
- `POST /api/properties/<id>/cdn-config` — update CDN origin settings
- `GET  /api/properties/<id>/preview` — browser preview with security headers
- `PUT  /api/properties/<id>/status` — change property status

### Reports
- `GET /api/reports/<prop_id>` — daily analytics
- `GET /api/reports/summary` — cross-property summary

### Webhooks
- `GET    /api/webhooks/` — list webhooks
- `POST   /api/webhooks/` — register webhook
- `DELETE /api/webhooks/<id>` — remove webhook

### Admin (charlie only)
- `GET /api/admin/users`
- `GET /api/admin/audit-log`
- `GET /api/admin/properties`
- `GET /api/admin/stats`

## Architecture

```
app/
  main.py          — Flask application factory
  database.py      — SQLite setup and seed data
  models.py        — Data access layer
  routes/
    auth.py        — Authentication endpoints
    properties.py  — Property + preview management
    reports.py     — Analytics endpoints
    webhooks.py    — Webhook CRUD
    admin.py       — Admin-only endpoints
templates/
  preview.html     — Property preview template
```

## Configuration

| Environment Variable | Default                        | Description             |
|----------------------|-------------------------------|-------------------------|
| `SECRET_KEY`         | dev-only-key-change-in-prod   | Flask session key       |
| `DB_PATH`            | data/cdn_dashboard.db         | SQLite database path    |