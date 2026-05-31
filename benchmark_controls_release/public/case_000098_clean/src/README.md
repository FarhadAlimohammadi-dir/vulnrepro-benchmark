# WebHook Relay Service

A production-grade webhook relay and delivery platform. Route incoming webhooks to internal services, test payloads, and monitor delivery success.

## Features

- Multi-user relay endpoint management
- HMAC-based payload signing
- Delivery logging with retry tracking
- Admin audit trail
- Live relay testing with curl-based dispatch

## Quick Start

```bash
docker-compose up --build
```

Service starts on http://localhost:9000

## Default Accounts

| Username | Password | Role |
|----------|----------|------|
| alice | AlicePass123! | admin |
| bob | BobPass123! | user |
| charlie | CharliePass123! | user |

## API Overview

### Authentication
- `POST /api/auth/login` — Get session cookie
- `GET /api/auth/me` — Current user info

### Relay Management
- `GET /api/webhooks/` — List your relays
- `POST /api/webhooks/` — Create relay endpoint
- `GET /api/webhooks/{id}/logs` — Delivery history
- `PUT /api/webhooks/{id}/secret` — Set HMAC secret

### Testing
- `POST /api/relay/preview` — Dry-run preview (no request made)
- `POST /api/relay/test` — Live curl-based dispatch test
- `GET /api/relay/stats/{id}` — Delivery statistics

## Architecture

Built with Flask + SQLite. Relay dispatch uses curl for maximum protocol compatibility with legacy webhook receivers.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | Flask session key |
| `DATABASE_PATH` | `/app/data/relay.db` | SQLite database path |