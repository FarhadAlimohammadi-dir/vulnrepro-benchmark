# 🪐 CodeNest

CodeNest is a collaborative code snippet manager with integrated AI-powered review tooling. Teams can store, browse, search, and get automated feedback on code snippets across a wide range of languages.

## Features

- **Snippet library** — create, edit, delete, and search snippets with language filtering and pagination
- **AI code review** — submit any file for automated style, annotation, and complexity analysis
- **Lint integration** — quick static checks for JavaScript and Python
- **Revision history** — per-snippet version log with change summaries
- **Team accounts** — username/password auth with admin and member roles
- **User profiles** — public profile pages, avatar customisation, bio
- **Admin panel** — user management, role assignment, and audit log
- **Audit log** — tamper-evident log of all significant actions
- **Comments** — per-snippet discussion threads
- **Tags** — categorise snippets for discovery

## Quick Start

```bash
docker compose up --build
# Visit http://localhost:9000
```

### Default accounts

| Username | Password  | Role   |
|----------|-----------|--------|
| alice    | alice123  | admin  |
| bob      | bob456    | member |
| carol    | carol789  | member |
| dave     | dave321   | member |
| eve      | eve654    | member |
| frank    | frank987  | member |

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/login` | Authenticate |
| GET | `/` | Snippet dashboard (paginated, filterable) |
| GET | `/snippets/new` | New snippet form |
| POST | `/snippets` | Create snippet |
| GET | `/snippets/:id` | Snippet detail + comments |
| GET | `/snippets/:id/edit` | Edit form |
| POST | `/snippets/:id` | Update snippet |
| POST | `/snippets/:id/delete` | Delete snippet |
| POST | `/snippets/:id/comment` | Add comment |
| GET | `/profile` | Edit own profile |
| GET | `/users/:username` | Public user page |
| GET | `/admin` | Admin panel (admin only) |
| POST | `/api/snippets` | Create snippet (JSON) |
| POST | `/api/snippets/preview` | Sanitized content preview |
| POST | `/api/snippets/lint` | Static lint check |
| POST | `/api/snippets/review` | AI-powered review |
| GET | `/api/snippets/:id/history` | Revision history |
| GET | `/api/search` | Full-text search |
| GET | `/api/tags` | Tag list with counts |
| GET | `/health` | Health check |

## Tech Stack

- Node.js 20 + Express 4
- EJS templates
- better-sqlite3
- morgan (request logging)
- Docker / Docker Compose