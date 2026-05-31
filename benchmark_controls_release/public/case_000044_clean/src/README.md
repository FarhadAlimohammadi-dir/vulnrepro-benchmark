# ProjectHub

A lightweight project management platform for small engineering teams.

## Features

- User authentication with role-based access control (user / admin)
- Project creation and membership management
- Task tracking with priorities and assignments
- Admin console: user management and audit log viewer
- Full audit trail for compliance

## Quick Start

```bash
docker-compose up --build
```

The application will be available at http://localhost:9000

## Default Accounts

| Username | Password        | Role  |
|----------|-----------------|-------|
| alice    | AlicePass123!   | admin |
| bob      | BobPass123!     | user  |
| charlie  | CharliePass123! | user  |

## API Reference

### Auth
- `POST /api/auth/login` — Authenticate
- `POST /api/auth/logout` — End session

### Users
- `POST /api/users/register` — Create account
- `GET  /api/users/<id>/profile` — View profile
- `PUT  /api/users/<id>/settings` — Update display name / department
- `PUT  /api/users/<id>/password` — Change password

### Admin
- `GET /api/admin/users` — List all users (admin only)
- `PUT /api/admin/users/<id>/role` — Change user role (admin only)
- `GET /api/admin/audit-logs` — View audit trail (admin only)

### Projects
- `GET  /api/projects` — List projects
- `POST /api/projects` — Create project
- `POST /api/search` — Search projects and tasks

## Architecture

```
app/
  __init__.py       # Flask app factory
  database.py       # SQLite setup & seeding
  models.py         # User, Project models
  routes/
    api.py          # JSON API endpoints
    web.py          # HTML page routes
templates/
  login.html
  dashboard.html
```

## Deployment Notes

- SQLite database stored at `/app/data/projecthub.db`
- Session secret configured via `SECRET_KEY` environment variable
- All passwords stored with bcrypt (cost factor 12)
- Audit log captures all authentication and administrative events