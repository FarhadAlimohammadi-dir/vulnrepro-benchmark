# TrackFlow - Marketing Attribution Platform

TrackFlow is a self-hosted marketing attribution and campaign analytics platform
for digital marketing teams. It provides multi-touch attribution, UTM parameter
management, and real-time campaign performance analytics.

## Features

- **Campaign Management**: Create and manage campaigns with UTM parameters
- **Visitor Tracking**: First-party cookie-based attribution tracking
- **Analytics Dashboard**: Impressions, clicks, conversions, and revenue metrics
- **Audit Logging**: Full audit trail of all user actions
- **Role-Based Access**: Admin and analyst roles

## Quick Start

```bash
docker compose up --build
```

The application will be available at http://localhost:9000

## Accounts

The development database seeds representative users for local testing. Passwords
are generated at initialization time unless supplied through deployment secrets.

## API Endpoints

### Authentication
- `POST /api/auth/login` - Sign in
- `POST /api/auth/logout` - Sign out
- `POST /api/auth/register` - Create account
- `GET /api/auth/me` - Current user info

### Tracking
- `POST /api/track` - Marketing pixel endpoint (records referral + sets cookies)
- `GET /api/track/events` - List tracking events (admin only)
- `GET /api/track/summary` - Referral summary (admin only)

### Campaigns
- `GET /api/campaigns` - List campaigns (auth required)
- `POST /api/campaigns` - Create campaign (auth required)
- `PUT /api/campaigns/:id` - Update campaign (auth required)
- `DELETE /api/campaigns/:id` - Delete campaign (auth required)

### Analytics
- `GET /api/analytics/overview` - Platform overview (auth required)
- `GET /api/analytics/campaigns/:id` - Campaign stats (auth required)
- `GET /api/analytics/top-refs` - Top referral sources (auth required)
- `GET /api/analytics/audit-log` - Audit log (admin only)

## Architecture

- **Framework**: Flask 3.0
- **Database**: SQLite with WAL mode
- **Auth**: bcrypt password hashing, server-side sessions
- **Security**: Request inspection middleware on all routes

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SECRET_KEY` | generated | Flask session secret |
| `FLASK_ENV` | production | Environment mode |
