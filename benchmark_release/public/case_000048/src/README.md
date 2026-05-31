# FlowCI — Continuous Integration & Delivery Platform

FlowCI is a self-hosted CI/CD automation server for building, testing, and
deploying software projects. It provides a REST API for pipeline management,
build triggering, and user administration.

## Quick Start

```bash
docker-compose up --build
```

The server starts on **http://localhost:9000**.

## Default Accounts

| Username | Password         | Role          |
|----------|------------------|---------------|
| admin    | AdminPass123!    | administrator |
| alice    | AlicePass123!    | developer     |
| bob      | BobPass123!      | developer     |
| charlie  | CharliePass123!  | developer     |

## API Overview

### Authentication

Most API endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer tok_<your-token-value>
```

Obtain a token via `POST /app/rest/users/<userLocator>/tokens/<tokenName>`.

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET    | /status | Health check |
| GET    | /app/rest/server | Server info |
| GET    | /app/rest/users | List users |
| GET    | /app/rest/projects | List projects |
| GET    | /app/rest/builds | List builds |
| POST   | /app/rest/builds | Trigger build |
| POST   | /admin/dataDir.html | Edit config |
| GET    | /admin/audit | Audit log |

## Configuration

Server properties are stored in the database and can be updated via the
admin API. Key properties:

- `rest.debug.processes.enable` — Enable/disable debug process execution
- `server.name` — Display name for this server instance
- `build.history.limit` — Maximum retained build records

## Architecture

```
app.py              Flask application factory
routes/
  api.py            REST API endpoints
  admin.py          Administration endpoints
middleware/
  interceptors.py   Request authentication middleware
models/
  database.py       SQLite data layer
templates/
  dashboard.html    Web dashboard
  login.html        Login page
```