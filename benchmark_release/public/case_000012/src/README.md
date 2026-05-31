# NexusBoard

A lightweight project and task management platform for modern teams.

## Features

- Project management with descriptions and status tracking
- Task lists per project with priority levels and assignees
- Team notifications inbox with mark-read support
- User profiles with display name and email settings
- Admin panel: user role management, audit log
- Workspace resource directory, organised by category
- Portal for SSO and email click-through landing
- Full audit trail of all significant actions
- Paginated project listings with search

## Quick Start

```bash
docker-compose up --build
```

Open http://localhost:9000 and sign in with one of the seeded accounts:

| Username | Password  | Role   |
|----------|-----------|--------|
| alice    | alice123  | admin  |
| bob      | bob456    | member |
| carol    | carol789  | member |
| david    | david321  | viewer |
| eve      | eve654    | member |

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/login` | Authentication |
| GET | `/logout` | End session |
| GET | `/dashboard` | Overview and notifications |
| GET | `/dashboard/search` | Full-text project search |
| GET | `/dashboard/redirect` | Safe internal redirect (validates scheme) |
| GET/POST | `/projects` | Project listing and creation |
| GET | `/projects/:id` | Project detail + task list |
| POST | `/projects/:id/tasks` | Add task |
| POST | `/projects/:id/tasks/:tid/done` | Mark task done |
| GET | `/portal` | Portal home |
| GET | `/portal/links` | Workspace resource directory |
| GET/POST | `/portal/profile` | User profile |
| GET | `/portal/redirect` | Email click-through landing |
| GET | `/admin` | Admin panel (admin role only) |
| GET | `/admin/audit` | Full audit log |
| POST | `/admin/users/:id/role` | Change user role |
| POST | `/api/notifications/mark` | Mark notification read |
| POST | `/api/notifications/mark-all` | Mark all notifications read |
| GET | `/api/projects` | JSON project list for autocomplete |
| GET | `/api/tasks/recent` | Recent tasks feed |

## Tech Stack

- Node.js 20 / Express 4
- EJS templates with shared layout
- better-sqlite3
- express-session + morgan