# ProjectFlow

A team project management API for engineering organizations. Manage projects, tasks, users, and API tokens with role-based access control and full audit logging.

## Quick Start

```bash
docker-compose up --build
```

The API will be available at http://localhost:9000

## Default Accounts

| Username | Password       | Role   |
|----------|---------------|--------|
| alice    | generated at first boot | admin  |
| bob      | generated at first boot | member |
| charlie  | generated at first boot | member |

## API Reference

### Authentication
- `POST /api/v1/auth/login` — Authenticate and create session
- `POST /api/v1/auth/logout` — End session
- `POST /api/v1/auth/register` — Register new account
- `GET /api/v1/auth/me` — Get current user profile
- `PUT /api/v1/auth/password` — Change password

### Projects
- `GET /api/v1/projects` — List accessible projects
- `POST /api/v1/projects` — Create project
- `GET /api/v1/projects/:id` — Get project details
- `PUT /api/v1/projects/:id` — Update project
- `DELETE /api/v1/projects/:id` — Delete project

### Users
- `GET /api/v1/users/search?q=` — Search users
- `GET /api/v1/users/:id` — Get user profile
- `GET /api/v1/users/:id/activity` — Get audit log (admin)
- `POST /api/v1/users/:id/deactivate` — Deactivate user (admin)

### API Tokens
- `GET /api/v1/tokens` — List tokens
- `POST /api/v1/tokens` — Create token
- `DELETE /api/v1/tokens/:id` — Revoke token
- `POST /api/v1/tokens/rotate` — Rotate all tokens

## Architecture

- **Flask** REST API with session-based authentication
- **SQLite** database with WAL mode for concurrent reads
- **bcrypt** password hashing (cost factor 12)
- Role-based access control (admin / member)
- Structured audit logging for all write operations

## Configuration

Set `SECRET_KEY` environment variable for session signing. See `docker-compose.yml` for all configuration options.
