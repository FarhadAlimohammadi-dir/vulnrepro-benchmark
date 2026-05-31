# CodePilot

CodePilot is a self-hosted AI-assisted code-review and task-automation platform.
It connects to your repositories, triages incoming issues, and runs automated
pipeline steps to keep your project healthy.

## Features

- **Issue tracker** — receive GitHub-style webhook payloads, browse with filters & pagination
- **Automated task runner** — tag an issue `codepilot` to kick off an agent pipeline
- **Snippet sandbox** — paste JS or Python and get instant evaluation feedback
- **Source linter** — lint JS/TS files against a minimal rule set via the API
- **Audit log** — every action recorded; viewable in the admin panel
- **Admin panel** — manage users, view audit events, check platform stats
- **Profile pages** — update email and bio

## Quick Start

```bash
docker compose up --build
```

Open <http://localhost:9000> and sign in with one of the seeded accounts:

| Username | Password    | Role  |
|----------|-------------|-------|
| alice    | alice123    | admin |
| bob      | bob123      | dev   |
| charlie  | charlie123  | dev   |
| diana    | diana123    | dev   |
| erin     | erin123     | dev   |

## API

| Method | Path                       | Auth | Description                          |
|--------|----------------------------|------|--------------------------------------|
| POST   | /api/issues                | No   | Create an issue (webhook target)     |
| GET    | /api/issues                | Yes  | List / search issues                 |
| GET    | /api/issues/:id            | Yes  | Get single issue                     |
| PATCH  | /api/issues/:id            | Yes  | Update status / priority             |
| POST   | /api/tasks/dispatch        | No   | Dispatch a labelled issue to agent   |
| GET    | /api/tasks                 | Yes  | List tasks                           |
| GET    | /api/tasks/:id/results     | Yes  | Get task execution results           |
| GET    | /api/repos                 | Yes  | List repositories                    |
| POST   | /api/repos/snippets/run    | Yes  | Run a sandboxed code snippet         |
| POST   | /api/repos/lint            | Yes  | Lint a source file                   |
| POST   | /api/repos/deps/diff       | Yes  | Diff two dependency lock files       |
| GET    | /admin/users               | Yes  | Admin: list users                    |
| GET    | /admin/audit               | Yes  | Admin: audit log                     |
| GET    | /admin/stats               | Yes  | Admin: platform statistics           |

## Configuration

| Variable           | Default           | Description                       |
|--------------------|-------------------|-----------------------------------|
| `PORT`             | `9000`            | HTTP listen port                  |
| `SESSION_SECRET`   | `cp-dev-secret`   | Session signing key               |
| `DB_PATH`          | `./codepilot.db`  | SQLite database path              |
| `PLAN_APPROVAL_MS` | `1000`            | Auto-approval delay (ms)          |
| `LOG_LEVEL`        | `info`            | Logging verbosity                 |