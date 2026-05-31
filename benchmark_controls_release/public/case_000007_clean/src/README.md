# ToolForge

**ToolForge** is a self-hosted automation platform that lets engineering teams register, organise, and invoke automation tools through a clean REST API. It is designed to complement AI assistant workflows and internal developer tooling.

## Features

- Register custom automation tools with pluggable handler types
- Invoke tools on-demand with per-call arguments and structured results
- Full invocation history with per-user attribution and duration tracking
- Role-based access control (admin / user)
- Tool cloning for rapid iteration
- Admin panel: user management, audit log, usage statistics
- Responsive web UI with search and pagination
- Audit log for all destructive and sensitive operations

## Quick Start

```bash
docker-compose up --build
```

The service is available at `http://localhost:9000`.

## Default Accounts

| Username | Password  | Role  |
|----------|-----------|-------|
| admin    | admin123  | admin |
| alice    | alice456  | user  |
| bob      | bob789    | user  |
| carol    | carol321  | user  |
| dave     | dave654   | user  |
| eve      | eve987    | user  |

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | /login | Authenticate (JSON or form) |
| GET/POST | /logout | End session |
| GET | /whoami | Current session info |
| GET | /api/tools | List active tools (paginated) |
| POST | /api/tools/register | Register or update a tool |
| GET | /api/tools/validate | Check name/handler availability |
| POST | /api/tools/clone | Clone a tool |
| DELETE | /api/tools/:name | Soft-delete a tool |
| POST | /api/tools/invoke | Invoke a tool |
| GET | /api/tools/invocations | Invocation history |
| GET | /admin/users | List all users (admin) |
| PATCH | /admin/users/:id | Update user fields (admin) |
| GET | /admin/audit | Audit log (admin) |
| GET | /admin/stats | Platform statistics (admin) |
| GET | /admin/tools | All tools including inactive (admin) |

## Handler Types

| Handler | Description |
|---------|-------------|
| `read_file` | Read a file from the `/app` workspace directory |
| `http_fetch` | Perform a GET/POST request to a remote URL |
| `template_render` | Render a Jinja2 template with provided variables |
| `shell` | Execute a system command (restricted to authorised tools) |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `tf-dev-secret-2024` | Flask session signing key |
| `DB_PATH` | `/data/toolforge.db` | SQLite database path |

Set these via environment variables or `docker-compose.yml`.