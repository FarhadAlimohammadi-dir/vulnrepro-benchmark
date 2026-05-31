# DocStore

A lightweight document management platform for teams.

## Features

- Create, edit, and organize documents by category
- Share documents with team members
- Role-based access control (user / admin)
- Public document sharing
- Audit logging for compliance
- Export documents in text or Markdown format

## Quick Start

```bash
docker-compose up --build
```

The application will be available at http://localhost:9000

## Default Accounts

| Username | Password       | Role  |
|----------|---------------|-------|
| alice    | AlicePass123! | user  |
| bob      | BobPass123!   | user  |
| charlie  | CharliePass123! | admin |

## API Overview

### Authentication
- `POST /api/auth/login` — Sign in
- `POST /api/auth/logout` — Sign out
- `POST /api/auth/register` — Create account
- `GET /api/auth/me` — Current user info

### Documents
- `GET /api/documents` — List accessible documents
- `POST /api/documents` — Create document
- `GET /api/documents/:id` — Get document
- `PUT /api/documents/:id` — Update document
- `DELETE /api/documents/:id` — Delete document
- `POST /api/documents/:id/share` — Share with user
- `GET /api/documents/:id/export` — Export as text/markdown

### Admin
- `GET /api/admin/stats` — System statistics
- `GET /api/admin/users` — List all users
- `GET /api/admin/audit-log` — View audit log

## Development

```bash
pip install -r requirements.txt
python run.py
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| SECRET_KEY | (dev key) | Flask session secret |
| DATABASE_PATH | data/docstore.db | SQLite database path |