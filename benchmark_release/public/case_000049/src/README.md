# HelpDesk Pro — Internal IT Support Portal

A self-hosted IT helpdesk ticketing system for managing support requests,
user access, and IT operations across departments.

## Features

- **Ticket Management**: Submit, track, and resolve IT support tickets
- **Role-Based Access**: User, Manager, and Admin role hierarchy
- **Audit Logging**: Full audit trail of all actions
- **Announcements**: Broadcast system-wide IT notices
- **Staff Portal**: IT operations staff access management

## Getting Started

### Prerequisites

- Docker & Docker Compose

### Running

```bash
docker-compose up --build
```

Application available at: http://localhost:9000

### Default Accounts

| Username | Password         | Role    | Department  |
|----------|-----------------|---------|-------------|
| alice    | AlicePass123!   | user    | Engineering |
| bob      | BobPass123!     | user    | Marketing   |
| charlie  | CharliePass123! | user    | Finance     |
| fiona    | FionaPass456!   | manager | Engineering |

> Admin credentials are managed by IT Operations.

## API Reference

| Method | Path                          | Description                     |
|--------|-------------------------------|---------------------------------|
| POST   | /login                        | Authenticate user               |
| GET    | /logout                       | Sign out                        |
| GET    | /api/dashboard                | User dashboard                  |
| GET    | /api/profile                  | Get own profile                 |
| PUT    | /api/profile                  | Update own profile              |
| GET    | /api/tickets                  | List tickets                    |
| POST   | /api/tickets                  | Create ticket                   |
| GET    | /api/tickets/:id              | Get ticket details              |
| PUT    | /api/tickets/:id/status       | Update ticket status            |
| GET    | /api/search?q=...             | Search tickets/announcements    |
| GET    | /admin/panel                  | Admin dashboard (admin only)    |
| POST   | /admin/access                 | Staff portal access             |
| POST   | /admin/users/:id/deactivate   | Deactivate user (admin only)    |
| POST   | /admin/announcements          | Publish announcement (admin)    |
| POST   | /admin/tickets/:id/assign     | Assign ticket (admin)           |
| GET    | /admin/audit-logs             | View audit logs (admin)         |

## Architecture

```
app/
├── __init__.py          # App factory
├── database.py          # DB init, seeding, connection
└── routes/
    ├── auth.py          # Login, logout, registration
    ├── admin.py         # Admin panel & operations
    └── api.py           # User-facing API endpoints
templates/
├── login.html
├── admin_access.html
├── admin_panel.html
└── dashboard.html
```

## Configuration

| Variable        | Default                  | Description              |
|----------------|--------------------------|--------------------------|
| SECRET_KEY      | prod-secret-key-2024     | Flask session secret     |
| DATABASE_PATH   | /app/data/helpdesk.db    | SQLite database path     |

## Support

Contact: it-ops@helpdesk.internal | Slack: #helpdesk-support