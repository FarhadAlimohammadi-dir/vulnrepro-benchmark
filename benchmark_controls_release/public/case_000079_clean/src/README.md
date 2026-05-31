# gRPC Platform - Enterprise Service Gateway

A microservice platform providing REST and gRPC-Web APIs for user management, reporting, and audit logging.

## Architecture

```
                    ┌─────────────────┐
Browser/Client ────▶│  Flask Gateway  │
                    │   (Port 9000)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         REST API      gRPC-Web       Admin API
        /api/auth    /api/grpc-web   /api/admin
        /api/users   /v1/*           /api/reports
```

## Services

| Service | Description |
|---------|-------------|
| `UserService` | User profile management |
| `AdminService` | User enumeration and admin operations |
| `SearchService` | Full-text search across reports |
| `ReportService` | Report CRUD via gRPC bridge |
| `AuditService` | Audit log retrieval |

## Quick Start

```bash
docker-compose up --build
```

API available at `http://localhost:9000`

## Authentication

REST endpoints use `Authorization: Bearer <token>` header.
gRPC-Web bridge supports `X-Grpc-Authorization` header for browser clients.
Internal service mesh uses `X-Internal-Service` header.

## Default Accounts

| Username | Password | Role |
|----------|----------|------|
| alice | AlicePass123! | user |
| bob | BobPass123! | user |
| charlie | CharliePass123! | admin |

## gRPC-Web Content Types

- `application/grpc-web` - Binary framing
- `application/grpc-web-text` - Base64-encoded framing (browser compatible)

Frame format: `[1-byte flags][4-byte length big-endian][message bytes]`
Trailer frame: First byte with MSB set (0x80)

## Development

```bash
pip install -r requirements.txt
python init_db.py
python app.py
```