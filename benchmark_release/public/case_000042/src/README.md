# NextAuth Portal

A modern SaaS authentication and dashboard platform with role-based access control.

## Features
- User login/logout with session management
- Protected dashboard and admin routes
- Token-based API authentication
- Multi-locale support (EN, FR)
- Health check endpoint

## Quick Start

```bash
docker-compose up
```

Access the app at `http://localhost:9000`

## Seeded Users

| Username | Password | Role   |
|----------|----------|--------|
| admin    | admin123 | admin  |
| user     | user123  | user   |
| demo     | demo123  | viewer |

## API Endpoints

### Public
- `GET /health` – Service health check
- `GET /login` – Login page
- `POST /login` – Submit credentials
- `POST /logout` – Clear session

### Protected (require auth token)
- `GET /dashboard` – User dashboard
- `GET /admin` – Admin panel
- `GET /profile` – User profile
- `GET /api/secrets` – API secrets endpoint

### Utilities
- `POST /api/validate-token` – Validate authentication token

## Locale Routes
- `GET /en/dashboard` – English dashboard
- `GET /fr/dashboard` – French dashboard

## Architecture

- **Middleware**: Protects routes before they reach the app layer
- **Session Management**: Express-session with secure cookies
- **Authentication**: Bearer token validation on protected endpoints
- **Routing**: Locale-aware redirects for internationalization

Built with Node.js 20 and Express 4.18.