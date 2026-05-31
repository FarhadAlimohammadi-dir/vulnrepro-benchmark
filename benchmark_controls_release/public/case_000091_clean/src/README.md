# DocFlow — Document Management Platform

DocFlow is an internal document management and collaboration platform for
teams that need to organize, share, and publish structured content.

## Features

- **Document Library**: Browse and search public documents by category
- **Access Control**: Role-based access (admin / editor / viewer)
- **Sharing**: Share private documents with specific team members
- **Audit Logging**: Full audit trail for compliance purposes
- **Export & Transform**: Convert document content to HTML, CSV, plain text, etc.
- **Admin Console**: User management, role assignment, platform statistics

## Quick Start

```bash
docker-compose up --build
```

The application will be available at http://localhost:9000

## Default Accounts

| Username | Password        | Role   |
|----------|-----------------|--------|
| alice    | AlicePass123!   | admin  |
| bob      | BobPass123!     | editor |
| charlie  | CharliePass123! | viewer |
| diana    | DianaPass456!   | editor |
| evan     | EvanPass789!    | viewer |

## API Reference

### Authentication
- `POST /auth/login` — obtain session cookie
- `POST /auth/logout` — invalidate session
- `GET  /auth/me` — current user info

### Documents
- `GET  /documents` — list public documents
- `GET  /documents/:id` — fetch a document
- `POST /documents` — create a document (editor+)
- `PUT  /documents/:id` — update a document (owner or admin)
- `GET  /api/documents/search?q=` — full-text search
- `POST /api/documents/:id/share` — share with a user
- `POST /api/documents/process` — transform content (to_html, to_plain, etc.)

### Admin
- `GET  /admin/audit` — audit log (admin only)
- `GET  /admin/users` — user list (admin only)
- `PUT  /admin/users/:id/role` — change user role (admin only)
- `GET  /admin/stats` — platform statistics (admin only)

## Tech Stack

- Python 3.12 + Flask
- SQLite (WAL mode)
- Flask-Login for session management
- bcrypt for password hashing