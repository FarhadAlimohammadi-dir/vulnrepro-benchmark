# NoteVault

A collaborative note-taking platform for small and medium teams, built with Node.js, Express, and SQLite.

## Features

- Personal note library with Markdown-flavoured content
- Team workspaces with role-based membership
- Full-text search across your own notes
- REST API with per-user token authentication for integrations
- Pro / free / enterprise plan tiers
- Admin panel with user management and audit log
- Activity history per user
- Pagination on note listings

## Quick Start

```bash
docker compose up --build
```

Open http://localhost:9000

## Default Accounts

| Username | Password    | Plan | Role  |
|----------|-------------|------|-------|
| alice    | alice123    | pro  | user  |
| bob      | bob456      | free | user  |
| carol    | carol789    | pro  | user  |
| dave     | dave321     | free | user  |
| erin     | erin654     | pro  | user  |
| frank    | frank987    | free | user  |
| grace    | grace111    | pro  | user  |
| hector   | hector222   | free | user  |
| ivan     | ivan333     | free | user  |
| julia    | julia444    | pro  | user  |
| admin    | adm1n!nv    | pro  | admin |

## REST API

All API endpoints require a session cookie (log in via `/login`) or use token auth.

| Method | Path                | Auth     | Description                |
|--------|---------------------|----------|----------------------------|
| GET    | /api/me             | required | Current user profile       |
| GET    | /api/notes          | required | List notes (paginated)     |
| GET    | /api/notes/:id      | required | Single note                |
| POST   | /api/notes          | required | Create note                |
| PATCH  | /api/notes/:id      | required | Update note fields         |
| DELETE | /api/notes/:id      | required | Delete note                |
| GET    | /api/workspaces     | required | List joined workspaces     |
| GET    | /api/stats/usage    | public   | Aggregate platform metrics |

## Tech Stack

- Node.js 20 + Express 4
- EJS templates
- better-sqlite3
- express-session
- morgan
- Docker Compose