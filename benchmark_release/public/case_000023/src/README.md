# CodeHub — Collaborative Code Review Platform

A production-style code review platform with snippet management, project organisation, AI-assisted analysis, commenting, and an admin panel.

## Quick Start

```bash
docker-compose up --build
```

The service starts on **http://localhost:9000**.

## Default Accounts

| Username | Password  | Role      |
|----------|-----------|-----------|
| alice    | password1 | admin     |
| bob      | password2 | developer |
| carol    | password3 | reviewer  |
| dave     | password4 | developer |
| eve      | password5 | developer |
| frank    | password6 | reviewer  |
| grace    | password7 | developer |
| henry    | password8 | developer |

## Feature Overview

- **Snippet CRUD** — Create, read, update, delete code snippets with tags, language badges, and view counts.
- **Project Management** — Group snippets into public or private projects.
- **Search & Pagination** — Full-text search across snippets with server-side pagination.
- **AI Assistant** — Paste code into the assistant panel for instant analysis, linting, and formatting.
- **Code Comments** — Threaded per-snippet comments with optional line-number references.
- **Profile Pages** — Edit bio and email; view recent activity.
- **Admin Panel** — User listing, workspace config editor, and a scrollable audit log.
- **Audit Log** — Every significant action is recorded with user, resource, detail, and IP.
- **Notifications** — Per-user notification feed surfaced on the dashboard.

## API Reference

| Method | Path                          | Description                      |
|--------|-------------------------------|----------------------------------|
| POST   | /api/login                    | Authenticate                     |
| POST   | /api/logout                   | End session                      |
| GET    | /api/snippets                 | List snippets (paged, searchable)|
| POST   | /api/snippets                 | Create snippet                   |
| GET    | /api/snippets/:id             | Get snippet                      |
| PUT    | /api/snippets/:id             | Update snippet                   |
| DELETE | /api/snippets/:id             | Delete snippet                   |
| GET    | /api/projects                 | List projects                    |
| POST   | /api/projects                 | Create project                   |
| GET    | /api/projects/public          | Public project listing           |
| POST   | /api/snippet/analyze          | AI assistant analysis            |
| POST   | /api/lint                     | Lint code                        |
| POST   | /api/format                   | Format code                      |
| GET    | /api/search                   | Search snippets                  |
| GET    | /api/profile                  | Get profile                      |
| PUT    | /api/profile                  | Update profile                   |
| GET    | /api/admin/users              | Admin: user list                 |
| GET    | /api/admin/audit              | Admin: audit log                 |
| GET    | /api/admin/config             | Admin: get workspace config      |
| PUT    | /api/admin/config             | Admin: update display settings   |
| GET    | /api/workspace/files          | List workspace files             |
| GET    | /api/notifications            | Get notifications                |
| POST   | /api/notifications/read       | Mark all notifications read      |

## Technology Stack

- **Backend**: Python 3.12, Flask 3.x
- **Database**: SQLite (WAL mode)
- **Container**: Docker / docker-compose

## Project Structure

```
app/
  app.py              Main Flask application
  db.py               Database init and helpers
  entrypoint.py       Container entry point
  models/
    user.py           User queries
    snippet.py        Snippet queries
    project.py        Project queries
  services/
    analyzer.py       AI assistant directive processor
    audit.py          Audit log service
    workspace.py      Workspace config and file helpers
  middleware/
    auth.py           Auth decorators
  templates/          Jinja2 HTML templates
  static/
    style.css         Application stylesheet
```