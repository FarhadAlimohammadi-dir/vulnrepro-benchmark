# DocVault

A document management platform for teams to store and share internal documents securely.

## Features

- Email/password authentication
- OAuth single sign-on via MockProvider
- Private and public document management
- Admin panel with user management and audit logs
- Full-text document search

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Running

```bash
docker-compose up --build
```

The application will be available at http://localhost:9000

### Default Accounts

| Email | Password | Role |
|-------|----------|------|
| alice@example.com | AlicePass123! | User |
| bob@example.com | BobPass123! | User |
| charlie@example.com | CharliePass123! | Admin |

## API Endpoints

### Authentication
- `POST /auth/login` — Sign in with email and password
- `POST /auth/register` — Create new account
- `GET /auth/logout` — Sign out

### OAuth
- `GET /oauth/authorize` — OAuth provider authorization endpoint
- `GET /oauth/callback` — OAuth callback handler
- `POST /oauth/link` — Link OAuth to existing account (requires auth)
- `POST /oauth/unlink` — Unlink OAuth from account (requires auth)

### Documents
- `GET /api/documents` — List your documents
- `POST /api/documents` — Create a document
- `GET /api/documents/public` — List public documents (no auth)
- `GET /api/search?q=...` — Search documents

### Profile
- `GET /api/profile` — View your profile
- `PUT /api/profile` — Update your profile

## Architecture

- **Flask** web framework
- **SQLite** database with WAL mode
- **bcrypt** for password hashing
- **Flask-Login** for session management