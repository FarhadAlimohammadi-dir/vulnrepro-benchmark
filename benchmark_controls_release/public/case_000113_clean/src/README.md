# CollabDocs

A collaborative rich-content document platform for teams.

## Features

- Create and share rich HTML content cards
- Custom web-component support for design-system elements
- Template variable substitution with `${name}` syntax
- Role-based access control (admin / user)
- Full-text search across public documents
- Comment threads on each card
- Audit logging for all mutations

## Quick Start

```bash
docker compose up --build
```

App runs at http://localhost:9000

## Accounts

The development database seeds representative users for local testing. Passwords
are generated at initialization time unless supplied through deployment secrets.

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/login | Authenticate |
| POST | /auth/register | Create account |
| POST | /auth/logout | Sign out |
| GET | /api/cards/:id | Fetch card |
| POST | /api/cards | Create card |
| PUT | /api/cards/:id | Update card |
| POST | /api/cards/:id/comment | Add comment |
| POST | /api/cards/:id/share | Share with user |
| POST | /api/cards/sanitize | Sanitize HTML for preview |
| GET | /api/admin/users | List users (admin) |
| GET | /api/admin/audit | View audit log (admin) |
| GET | /search | Search documents |

## Architecture

- **Node.js 20** + Express 4
- **better-sqlite3** for persistence
- **DOMPurify** (server-side via jsdom) for HTML sanitization
- **EJS** templates
- Session-based authentication with bcrypt password hashing
