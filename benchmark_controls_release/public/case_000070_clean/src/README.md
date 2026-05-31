# DocFlow

A lightweight collaborative document management platform.

## Features

- Create, edit, and share documents
- Role-based access control (user / admin)
- Public and private document visibility
- Full-text document search
- Audit logging for admin users
- SSR-compatible hydration for edge-cached deployments

## Quick Start

```bash
docker-compose up --build
```

The app will be available at http://localhost:9000

## Default Accounts

| Username | Password       | Role  |
|----------|----------------|-------|
| alice    | AlicePass123!  | user  |
| bob      | BobPass123!    | user  |
| charlie  | CharliePass123!| admin |
| diana    | DianaPass999!  | user  |
| eve      | EvePass777!    | user  |
| frank    | FrankPass555!  | user  |

## Architecture

```
app/
  __init__.py       Flask application factory
  models.py         ORM-style data models (User, Document)
  routes/
    auth.py         Login, logout, password change
    pages.py        Server-rendered page views
    api.py          REST API endpoints
    admin.py        Admin-only management endpoints
templates/
  index.html        Landing page
  login.html        Authentication page
  dashboard.html    Application shell
init_db.py          Database bootstrap script
run.py              Entry point
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | /login | Authenticate |
| POST | /logout | End session |
| GET | /api/documents | List accessible documents |
| POST | /api/documents | Create document |
| PUT | /api/documents/:id | Update document |
| DELETE | /api/documents/:id | Delete document |
| POST | /api/documents/:id/share | Share with a user |
| GET | /api/search?q= | Search documents |
| GET | /api/user/profile | Get own profile |
| PUT | /api/user/profile | Update own profile |
| GET | /admin/users | List all users (admin) |
| GET | /admin/audit-log | View audit log (admin) |
| PUT | /admin/users/:id/role | Change user role (admin) |