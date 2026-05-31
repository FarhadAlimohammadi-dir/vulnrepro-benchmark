# DocVault

A document management portal for small teams. Upload, organize, and securely share files with colleagues using time-limited share links.

## Features

- **Secure login** — session-based authentication with audit logging
- **Document management** — upload, tag, comment on, and delete files
- **Pagination & filtering** — browse documents by tag with paginated results
- **Shareable links** — generate 24-hour share tokens for external recipients
- **Profile & settings** — update display name, email, and password
- **Admin panel** — user management, document oversight, full audit log
- **REST API** — JSON endpoints for all core operations

## Quick Start

```bash
docker compose up --build
```

Open [http://localhost:9000](http://localhost:9000) and sign in with one of the demo accounts:

| Username | Password     | Role  |
|----------|-------------|-------|
| alice    | alice123    | user  |
| bob      | bob456      | user  |
| charlie  | charlie789  | admin |
| diana    | diana999    | user  |
| evan     | evan555     | user  |

## API Reference

| Method   | Path                  | Auth     | Description                              |
|----------|-----------------------|----------|------------------------------------------|
| `POST`   | `/api/upload`         | Required | Upload a file (multipart/form-data)      |
| `GET`    | `/api/docs`           | Required | List own documents (paginated)           |
| `GET`    | `/api/docs/:id`       | Required | Retrieve a document by ID                |
| `DELETE` | `/api/docs/:id`       | Required | Delete own document                      |
| `POST`   | `/api/shares`         | Required | Create a share token                     |
| `GET`    | `/api/shares/:token`  | Public   | Fetch document via share token           |
| `GET`    | `/api/profile`        | Required | View own account details                 |
| `GET`    | `/api/audit`          | Required | View own audit events                    |
| `GET`    | `/api/search?q=`      | Required | Search own documents by filename         |
| `POST`   | `/api/audit/log`      | Required | Record a client-side event               |

## Tech Stack

- Node.js 20 + Express 4
- EJS templates
- better-sqlite3 (embedded, no external DB required)
- morgan (HTTP request logging)
- Docker / Docker Compose