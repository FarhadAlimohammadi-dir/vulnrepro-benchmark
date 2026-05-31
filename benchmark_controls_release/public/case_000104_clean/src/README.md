# DataViz Studio

A collaborative charting and dashboard platform for teams. Create, share, and annotate data visualizations.

## Features

- Create and manage visualization dashboards
- Rich chart configuration via JSON specs
- Team collaboration with comments and sharing
- Public/private dashboard visibility controls
- Audit logging for all user actions

## Quick Start

```bash
docker-compose up --build
```

Access at http://localhost:9000

## Default Accounts

| Username | Password        | Role   |
|----------|-----------------|--------|
| alice    | AlicePass123!   | admin  |
| bob      | BobPass123!     | editor |
| charlie  | CharliePass123! | viewer |

## API

- `GET /api/dashboards` — list your dashboards
- `POST /api/dashboards` — create a dashboard
- `GET /api/search?q=` — search dashboards
- `POST /api/comments` — add a comment
- `POST /api/share` — share with a user
- `GET /api/audit` — audit log (admin only)

## Tech Stack

- Node.js 20 + Express 4
- EJS templating
- better-sqlite3
- bcryptjs for password hashing