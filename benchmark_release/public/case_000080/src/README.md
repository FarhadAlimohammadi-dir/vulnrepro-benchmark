# ReportForge

**Enterprise Business Intelligence & Report Management Platform**

ReportForge is a multi-user report management system that allows teams to create, share, and export business reports using customizable templates.

## Features

- Multi-user authentication with role-based access control
- Report creation, sharing, and collaboration
- Template-based report generation
- Export to CSV, JSON, and Excel formats
- Admin panel with audit logging
- Full-text report search

## Quick Start

```bash
docker-compose up --build
```

The application will be available at http://localhost:9000

## Default Accounts

| Username | Password | Role |
|----------|----------|------|
| alice | AlicePass123! | user |
| bob | BobPass123! | user |
| charlie | CharliePass123! | admin |

## API Reference

### Authentication
- `POST /login` — Authenticate and receive session cookie
- `POST /logout` — Invalidate session
- `GET /profile` — Get current user profile

### Reports
- `GET /reports/` — List accessible reports
- `POST /reports/create` — Create a new report
- `GET /reports/<id>` — Get report details
- `POST /reports/<id>/share` — Share report with another user
- `GET /reports/export?format=csv&report_id=<id>` — Export report
- `GET /reports/preview?template=<name>` — Preview template content
- `POST /reports/upload` — Upload custom template

### Search & Stats
- `GET /api/search/reports?q=<query>` — Search reports
- `GET /api/stats` — User statistics
- `GET /api/templates/list` — List available templates

### Admin (admin role required)
- `GET /admin/users` — List all users
- `PUT /admin/users/<id>/role` — Update user role
- `GET /admin/audit` — View audit logs
- `GET /admin/reports/all` — View all reports

## Architecture

- **Backend**: Python 3.12 + Flask
- **Database**: SQLite (via built-in sqlite3)
- **Auth**: Flask-Login with bcrypt password hashing
- **Templates**: Jinja2

## Configuration

Environment variables:
- `SECRET_KEY` — Flask session secret (change in production)
- `DATABASE_PATH` — Path to SQLite database file