# ContentFlow Editorial Platform

A modern collaborative publishing platform for editorial teams.

## Features

- **Article Management** — create, edit, publish, and archive articles
- **Category Organization** — organize content by topic categories
- **Author Profiles** — public author pages with publication history
- **Comment Moderation** — approve or remove reader comments
- **Admin Dashboard** — platform statistics and audit logging
- **Advanced Search** — flexible content discovery via API
- **Pagination** — efficient browsing of large content collections
- **Audit Trail** — comprehensive logging of all platform actions

## Tech Stack

- **Runtime:** Node.js 20
- **Framework:** Express.js 4
- **ORM:** Prisma 5 with PostgreSQL 16
- **Templating:** EJS with shared layout
- **Sessions:** express-session
- **Logging:** Winston + Morgan

## Quick Start

```bash
docker-compose up --build
```

Visit `http://localhost:9000` — the platform seeds demo content on first run.

## Demo Accounts

| Email | Role |
|-------|------|
| alice@example.com | Admin |
| bob@example.com | Writer |
| charlie@example.com | Writer |

## API Reference

### Public Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/articles/public` | Paginated published articles |
| GET | `/api/articles/featured` | Featured article list |
| GET | `/api/articles/:id` | Article by numeric ID |
| GET | `/api/articles/slug/:slug` | Article by slug |
| GET | `/api/users/:id/public` | Public author profile |
| POST | `/api/articles/search` | Advanced article search |
| POST | `/api/articles/filter-safe` | Constrained article filter |

### Authenticated Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/articles/create` | Create article |
| PUT | `/api/articles/:id` | Update article |
| DELETE | `/api/articles/:id` | Archive article |
| GET | `/api/users/profile` | Own profile |
| PUT | `/api/users/profile` | Update profile |
| GET | `/api/users/settings` | Account settings |

### Admin Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/stats` | Platform statistics |
| GET | `/api/admin/audit-log` | Audit log |
| GET | `/api/admin/comments/pending` | Pending comments |
| POST | `/api/admin/comments/:id/approve` | Approve comment |
| DELETE | `/api/admin/comments/:id` | Delete comment |