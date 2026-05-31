# TaskFlow

A project management platform for modern engineering teams. Organize projects,
track tasks, manage team members, and stay on top of deadlines.

## Features

- Project and task management with priority and status tracking
- Team member assignment and role-based access control
- Real-time audit logging of all actions
- Webhook integrations for third-party services
- Full-text task search
- Admin panel for user management

## Quick Start

```bash
docker-compose up --build
```

App will be available at http://localhost:9000

## Default Accounts

| Username | Password        | Role   |
|----------|-----------------|--------|
| alice    | AlicePass123!   | admin  |
| bob      | BobPass123!     | member |
| charlie  | CharliePass123! | member |

## API Endpoints

- `GET /dashboard` — User dashboard
- `GET /search?q=<query>` — Search tasks
- `GET /projects/` — List all projects
- `POST /projects/` — Create project (JSON)
- `PATCH /api/tasks/<id>` — Update task status
- `GET /api/audit` — View audit log (admin: all, member: own)
- `GET /admin/users` — List users (admin only)

## Tech Stack

- Python 3.12 + Flask
- SQLite with WAL mode
- bcrypt password hashing
- Session-based authentication