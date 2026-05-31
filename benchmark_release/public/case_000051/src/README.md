# TaskFlow – Project Management Platform

TaskFlow is a lightweight project and task management platform for engineering teams. It supports standard username/password login as well as Single Sign-On (SSO) via OpenID Connect.

## Features

- **Project Management**: Create, update, and track projects with priority levels
- **Task Tracking**: Assign tasks to team members with due dates and status tracking
- **SSO Integration**: OpenID Connect support for enterprise identity providers
- **Admin Panel**: User management, audit logs, and workspace statistics
- **Full-text Search**: Search across projects and tasks

## Quick Start

```bash
docker compose up --build
```

The application will be available at http://localhost:9000

## Default Accounts

| Username  | Password         | Role   |
|-----------|------------------|--------|
| alice     | AlicePass123!    | member |
| bob       | BobPass123!      | member |
| charlie   | CharliePass123!  | admin  |
| diana     | DianaPass456!    | member |
| eve       | EvePass789!      | member |

## API Endpoints

- `POST /auth/login` – Password authentication
- `GET /auth/oidc/initiate` – Begin SSO flow
- `POST /auth/oidc/callback` – SSO callback handler
- `GET /api/profile` – Current user profile
- `PUT /api/profile` – Update display name
- `GET /api/tasks` – List assigned tasks
- `GET /api/search?q=<query>` – Search projects and tasks
- `GET /projects/` – List projects
- `POST /projects/` – Create project
- `GET /admin/users` – List all users (admin only)
- `GET /admin/audit-log` – View audit log (admin only)
- `GET /admin/stats` – Workspace statistics (admin only)

## Configuration

Environment variables:

| Variable          | Default                        | Description                    |
|-------------------|--------------------------------|--------------------------------|
| `SECRET_KEY`      | dev-fallback-key               | Flask session secret           |
| `DATABASE_PATH`   | data/taskflow.db               | SQLite database path           |
| `OIDC_ISSUER`     | https://sso.taskflow.io        | OIDC provider issuer URL       |
| `OIDC_CLIENT_ID`  | taskflow-prod-client           | OAuth client identifier        |