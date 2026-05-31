# NovaSpark Gaming Platform

A digital game distribution platform API providing account management,
game catalog browsing, purchasing, and reviews.

## Quick Start

```bash
docker-compose up --build
```

API available at http://localhost:9000

## API Overview

### Authentication
- `POST /api/auth/login` — Login with email/password or SSO token
- `POST /api/auth/register` — Create new account
- `POST /api/auth/logout` — End session
- `POST /api/auth/request-reset` — Request password reset email
- `POST /api/auth/reset-password` — Complete password reset
- `POST /api/auth/change-password` — Change password (authenticated)

### Profile
- `GET /api/profile/` — Get current user profile + library
- `PUT /api/profile/update` — Update display name / country
- `GET /api/profile/library` — Full game library
- `GET /api/profile/orders` — Order history

### Games
- `GET /api/games/` — Browse catalog (filter by genre, price)
- `GET /api/games/search?q=term` — Search games
- `GET /api/games/:slug` — Game details + reviews
- `POST /api/games/purchase` — Purchase a game
- `POST /api/games/:slug/review` — Submit review (must own game)

### Admin (admin role required)
- `GET /api/admin/users` — List all users
- `POST /api/admin/users/:id/suspend` — Suspend account
- `POST /api/admin/users/:id/activate` — Reactivate account
- `GET /api/admin/audit-log` — View audit trail
- `GET /api/admin/stats` — Platform statistics

## Default Accounts

| Email | Password | Role |
|-------|----------|------|
| alice@example.com | AlicePass123! | admin |
| bob@example.com | BobPass123! | user |
| charlie@example.com | CharliePass123! | user |

## Tech Stack

- Python 3.12 + Flask
- SQLite (WAL mode)
- bcrypt password hashing
- Flask-Login session management