# TaskFlow – Project Management Platform

TaskFlow is a lightweight project and task management platform designed for engineering teams. It provides a RESTful API for managing projects, tasks, team members, and generating reports.

## Features

- **User Management**: Role-based access control (member / admin)
- **Projects**: Create, manage, and track project status
- **Tasks**: Assign tasks with priorities, due dates, and status tracking
- **Admin Panel**: User administration, audit logs, and application settings
- **Reporting**: Export user activity reports for analytics integration

## Quick Start

```bash
docker-compose up --build
```

The API will be available at `http://localhost:9000`.

## API Reference

### Authentication
- `POST /api/auth/login` – Log in with username and password
- `POST /api/auth/logout` – End the current session
- `POST /api/auth/register` – Register a new account
- `POST /api/auth/refresh` – Check current session

### Projects
- `GET /api/v1/projects` – List accessible projects
- `POST /api/v1/projects` – Create a new project
- `GET /api/v1/projects/:id` – Get project details

### Tasks
- `GET /api/v1/tasks` – List tasks (optionally filter by project)
- `PATCH /api/v1/tasks/:id` – Update task fields

### Profile
- `GET /api/v1/profile` – View own profile
- `PATCH /api/v1/profile` – Update department

### Admin (requires admin role)
- `GET /api/admin/users` – List all users
- `POST /api/admin/users/:id/deactivate` – Deactivate a user
- `POST /api/admin/users/:id/promote` – Promote to admin
- `GET /api/admin/settings` – View app configuration
- `GET /api/admin/audit-logs` – View audit trail

### Reports
- `GET /api/v1/admin/export` – User activity export (ETL pipeline feed)

## Default Accounts

| Username | Password | Role |
|----------|----------|------|
| alice | AlicePass123! | member |
| bob | BobPass123! | member |
| charlie | CharliePass123! | admin |

## Architecture

```
app/
├── __init__.py        # App factory, blueprint registration
├── middleware.py      # Request lifecycle hooks (auth enforcement)
├── models.py          # Domain models
├── database.py        # SQLite setup and seed data
└── routes/
    ├── auth.py        # /api/auth/*
    ├── admin.py       # /api/admin/*
    ├── api.py         # /api/v1/*
    └── pages.py       # HTML pages
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | dev key | Flask session secret |
| `DATABASE_URL` | `sqlite:///taskflow.db` | Database connection |
| `FLASK_ENV` | `production` | Environment mode |