# NeuralOps Platform

A production-grade operations dashboard for managing AI model training pipelines, metrics, model registry, and team collaboration.

## Features

- **Training Run Tracker** — submit, monitor, filter, and cancel model training jobs with pagination
- **Metrics Explorer** — per-run and per-model performance metrics with time-series data
- **Log Search** — filter operational events by service, severity level, actor, and date range
- **Model Registry** — promote and browse versioned model artifacts with tag-based filtering
- **Analytics Interface** — SQL-based analytics queries for the ops pipeline tooling
- **Admin Panel** — user management, role assignment, model promotion, and audit log viewer
- **Profile Pages** — user display name, email, bio, and API token
- **Audit Log** — tamper-evident record of all platform actions
- **Notifications** — per-user in-app alerts for run events

## Getting Started

### Prerequisites
- Docker and Docker Compose

### Run
```bash
docker-compose up --build
```

Access the dashboard at http://localhost:9000

### Default Accounts

| Username | Password   | Role     |
|----------|------------|----------|
| admin    | admin123   | admin    |
| ops      | ops2024    | operator |
| viewer   | view2024   | viewer   |
| mleng1   | mleng2024  | operator |
| mleng2   | mleng2025  | operator |
| devops1  | devops2024 | operator |

## API Endpoints

| Method | Path                        | Auth       | Description                        |
|--------|-----------------------------|------------|------------------------------------|
| GET    | /health                     | No         | Service health check               |
| GET/POST | /login / /logout          | No / Yes   | Authentication                     |
| GET    | /dashboard                  | Yes        | Platform overview                  |
| GET    | /runs                       | Yes        | Training runs list (paginated)     |
| POST   | /runs                       | Yes        | Submit new training run            |
| GET    | /runs/:id                   | Yes        | Run detail with metrics            |
| POST   | /runs/:id/notes             | Yes        | Update run notes                   |
| POST   | /runs/:id/cancel            | Operator+  | Cancel an active run               |
| GET    | /profile                    | Yes        | View/edit profile                  |
| GET    | /admin                      | Admin      | Admin panel                        |
| POST   | /admin/models/promote       | Admin      | Promote model to registry          |
| POST   | /admin/users/:id/role       | Admin      | Change user role                   |
| GET    | /api/metrics                | Yes        | Metrics query                      |
| POST   | /api/logs/search            | Yes        | Filtered event log search          |
| GET    | /api/notifications          | Yes        | Unread notifications               |
| GET    | /api/registry               | Yes        | Model registry listing             |
| GET    | /analytics/summary          | Yes        | Aggregated analytics               |
| GET    | /analytics/runs-over-time   | Yes        | Time-bucketed run counts           |
| GET    | /analytics/model-leaderboard| Yes        | Best metrics per model             |
| GET    | /analytics/query            | Internal   | Ops pipeline analytics query       |

## Tech Stack

- **Runtime:** Node.js 20
- **Framework:** Express 4 + EJS templates
- **Database:** SQLite via better-sqlite3
- **Session:** express-session
- **Logging:** Winston + Morgan

## Configuration

| Env Var          | Default                        | Description           |
|------------------|--------------------------------|-----------------------|
| PORT             | 9000                           | HTTP listen port      |
| SESSION_SECRET   | neuralops-session-key-2024     | Session signing key   |
| DB_PATH          | ./neuralops.db                 | SQLite database path  |
| LOG_LEVEL        | info                           | Winston log level     |