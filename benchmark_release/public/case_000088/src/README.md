# DevPortal – Repository Onboarding Platform

Internal developer platform for onboarding, managing, and monitoring source
code repositories across the organisation.

## Features

- Repository registration and discovery
- Remote repository configuration probing
- Webhook management per repository
- Role-based access control (admin / developer)
- Full audit log for all mutating actions

## Quick Start

```bash
docker-compose up --build
```

The portal is available at **http://localhost:9000**.

### Default Accounts

| Username | Password        | Role      |
|----------|-----------------|-----------|
| alice    | AlicePass123!   | admin     |
| bob      | BobPass123!     | developer |
| charlie  | CharliePass123! | developer |

## API Reference

| Method | Path                  | Auth     | Description                          |
|--------|-----------------------|----------|--------------------------------------|
| POST   | /api/auth/login       | –        | Obtain a session                     |
| POST   | /api/auth/logout      | session  | Destroy session                      |
| GET    | /api/repo/list        | session  | List accessible repositories         |
| POST   | /api/repo/register    | session  | Register a new repository            |
| GET    | /api/repo/search      | session  | Full-text search over repositories   |
| GET    | /api/repo/check       | session  | Probe remote repo for portal config  |
| GET    | /api/user/profile     | session  | Fetch own profile                    |
| PUT    | /api/user/profile     | session  | Update own email                     |
| POST   | /api/webhook          | session  | Create repository webhook            |
| GET    | /api/webhook          | session  | List webhooks for a repository       |
| GET    | /api/admin/users      | admin    | List all users                       |
| GET    | /api/admin/audit      | admin    | View audit log                       |

## Architecture

```
Browser → Express (9000) → SQLite (portal.db)
                         → Express (8080, internal) → git
```

The frontend service on port 9000 proxies repository-probe requests to an
internal backend service on port 8080 that performs the actual git operations.