# Gateway Portal — Workforce Access Management

An enterprise-grade portal for managing employee system access requests, role assignments, and provisioning workflows.

## Features

- **Account Registration** — Self-service onboarding for `@target.com` employees
- **Access Requests** — Submit, track, and manage requests for system access
- **Role-Based Access Control** — Fine-grained permissions (`IC_REQUESTER`, `REQUESTER`, `VIEWER`, `ADMIN`, `ADMIN AND REQUESTER`)
- **Admin Dashboard** — User management, request reviews, department overview
- **Audit Logging** — Full compliance event trail for all actions
- **Profile Management** — Self-service personal info and password changes

## Quick Start

```bash
docker-compose up --build
```

Access the portal at: http://localhost:9000

## Default Accounts

| Email | Password | Role |
|-------|----------|------|
| alice@target.com | pass123 | IC_REQUESTER |
| bob@target.com | pass123 | IC_REQUESTER |
| carol@target.com | pass123 | REQUESTER |
| dan@target.com | pass123 | REQUESTER |
| priya@target.com | pass123 | REQUESTER |
| admin@target.com | admin123 | ADMIN |
| sysadmin@target.com | admin456 | ADMIN AND REQUESTER |

## API Endpoints

### Auth
- `POST /api/auth/login` — Authenticate
- `POST /api/auth/logout` — Sign out
- `GET  /api/auth/me` — Current session info

### Accounts
- `POST /api/accounts/create` — Register new account
- `GET  /api/accounts/check-username` — Availability check

### Access Requests
- `GET  /api/requests/list` — List user's requests
- `POST /api/requests/new` — Submit new request
- `GET  /api/requests/:id` — View request details

### Profile
- `GET  /api/profile` — Get profile
- `POST /api/profile/update` — Update personal info
- `POST /api/profile/change-password` — Change password

### Admin
- `GET  /api/admin/dashboard` — Dashboard data
- `GET  /api/admin/users` — User list (paginated)
- `PUT  /api/admin/users/:id` — Update user
- `GET  /api/admin/requests` — All requests
- `POST /api/admin/requests/:id/review` — Review request
- `GET  /api/admin/systems` — System catalog
- `GET  /api/admin/departments` — Department list

### Audit
- `GET  /api/audit/events` — Audit log (admin)
- `POST /api/audit/log` — Submit audit event (admin)

## Architecture

- **Runtime**: Node.js 20 + Express 4
- **Database**: SQLite3 (better-sqlite3)
- **Views**: EJS templates
- **Auth**: Session-based (express-session)