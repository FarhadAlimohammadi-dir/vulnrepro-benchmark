# GitHost

A self-hosted Git repository management platform with integrated credential storage,
webhook management, and API token issuance.

## Features

- Repository hosting (public/private)
- Git credential helper protocol support
- Webhook delivery with HMAC verification
- Personal API token management
- Role-based access (admin/user)

## Quick Start

```bash
docker-compose up --build
```

Service available at: http://localhost:9000

## API Overview

### Authentication

```
POST /api/auth/register   Create account
POST /api/auth/login      Authenticate (returns session cookie)
POST /api/auth/logout     End session
GET  /api/auth/me         Current user info
```

### Repositories

```
GET    /api/repos          List repos (public + owned)
POST   /api/repos          Create repository
GET    /api/repos/:id      Repository details
DELETE /api/repos/:id      Delete repository
```

### Git Credential Helper

```
POST /api/credential/lookup   Resolve git credentials for a host
POST /api/credential/store    Store new credential (auth required)
GET  /api/credential/list     List credentials (auth required)
DELETE /api/credential/:id    Remove credential (auth required)
```

### Tokens

```
GET    /api/tokens       List API tokens
POST   /api/tokens       Generate token
DELETE /api/tokens/:id   Revoke token
```

### Webhooks

```
POST /api/webhooks                   Register webhook
POST /api/webhooks/:id/verify        Verify payload signature
```

## Default Accounts

| Username | Password       | Role  |
|----------|---------------|-------|
| alice    | AlicePass123! | admin |
| bob      | BobPass123!   | user  |
| charlie  | CharliePass123! | user |

## Architecture

- **Flask** application server (port 9000)
- **SQLite** with WAL mode for concurrent reads
- **bcrypt** password hashing
- Session-based authentication

## Configuration

Environment variables:
- `DATABASE_PATH` — SQLite file location (default: `githost.db`)
- `SECRET_KEY` — Flask session secret key