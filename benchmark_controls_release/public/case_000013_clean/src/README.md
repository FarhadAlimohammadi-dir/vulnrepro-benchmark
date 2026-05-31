# DevForge

A team-oriented code review and workspace automation platform for development teams.

## Features

- **Project management** — create, edit, delete and paginate projects by language
- **Snippet library** — store and share code snippets per project
- **File browser** — navigate workspace files safely
- **Task runner** — execute approved shell commands inside project workspaces
- **Audit log** — every login and task execution is recorded
- **Admin panel** — manage users and view system-wide audit events
- **Profile settings** — update display name and email

## Quick Start

```bash
docker compose up --build
```

Open [http://localhost:9000](http://localhost:9000) and sign in with a demo account:

| Username | Password  | Role  |
|----------|-----------|-------|
| alice    | alice123  | admin |
| bob      | bob456    | dev   |
| carol    | carol789  | dev   |
| dave     | dave321   | dev   |
| eve      | eve654    | dev   |

## Task Runner

The task runner executes a curated set of shell utilities inside a project's
workspace directory, removing the need to SSH into build machines for routine
inspection tasks.

Approved commands: `ls`, `echo`, `cat`, `pwd`, `touch`, `mkdir`, `wc`,
`date`

## Tech Stack

- **Runtime:** Node.js 20
- **Framework:** Express 4 + EJS
- **Database:** SQLite via better-sqlite3
- **Logger:** morgan
- **Container:** Docker / Docker Compose

## Development

```bash
cd app && npm install
node app.js
```

The service listens on port **9000** by default (`PORT` env var overrides).
