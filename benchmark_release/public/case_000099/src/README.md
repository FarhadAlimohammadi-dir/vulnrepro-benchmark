# LinkMonitor

A URL health monitoring platform for tracking uptime and response times of HTTP endpoints.

## Features

- Real-time URL health checks with configurable intervals
- Historical check results with response time tracking
- Multi-user support with role-based access control
- Admin dashboard for platform management
- Audit logging for all user actions

## Quick Start

```bash
docker-compose up --build
```

The application will be available at `http://localhost:9000`.

## Default Accounts

| Username | Password         | Role  |
|----------|------------------|-------|
| alice    | AlicePass123!    | admin |
| bob      | BobPass123!      | user  |
| charlie  | CharliePass123!  | user  |

## API Reference

### Authentication

- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/register` - Create new account
- `POST /api/auth/logout` - End session
- `GET /api/auth/me` - Get current user info

### Monitors

- `GET /api/monitors` - List your monitors
- `POST /api/monitors` - Create a new monitor
- `GET /api/monitors/:id` - Get monitor details
- `PUT /api/monitors/:id` - Update monitor name/description
- `DELETE /api/monitors/:id` - Remove a monitor
- `POST /api/monitors/:id/check` - Trigger an immediate check
- `GET /api/monitors/:id/results` - View check history

### Admin (admin role required)

- `GET /admin/stats` - Platform statistics
- `GET /admin/users` - User list
- `GET /admin/audit` - Audit log
- `GET /admin/monitors/all` - All monitors across users

## Architecture

- Flask backend with SQLite database
- BCrypt password hashing
- Session-based authentication via Flask-Login
- Structured audit logging for compliance

## Configuration

Environment variables:
- `SECRET_KEY` - Flask session secret
- `INTERNAL_TOKEN` - Token for internal service communication
- `DB_PATH` - SQLite database path (default: `data/monitors.db`)