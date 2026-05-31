# AstroSSR Platform

A Node.js Express application providing server-side rendering with session management,
role-based access control, audit logging, and request inspection utilities.

## Features

- User authentication with session management
- Role-based access control (admin, moderator, user, guest)
- Server-side request processing and proxy header support
- Audit logging for compliance
- User profile management
- Health check and status endpoints
- Admin panel for user management

## Getting Started

### Prerequisites

- Node.js 20+
- Docker & Docker Compose (optional)

### Installation

```bash
npm install
npm start
```

The application listens on port 9000.

### Using Docker

```bash
docker-compose up
```

## Demo Users

| Username | Password  | Role      |
|----------|-----------|-----------|
| admin    | admin123  | admin     |
| user     | user123   | user      |
| guest    | guest123  | guest     |
| jsmith   | jsmith456 | user      |
| mjones   | mjones789 | user      |
| rwilson  | rwilson654| moderator |

## Routes

### Public
- `GET /` — Home page with featured content
- `GET /login` — Login form
- `POST /login` — Authenticate
- `GET /logout` — End session
- `GET /health` — Health check
- `GET /status` — Application status

### Authenticated
- `GET /profile` — User profile
- `POST /profile/settings` — Update profile settings
- `GET /fetch-content` — Request metadata inspector

### Admin Only
- `GET /admin` — Admin panel
- `GET /api/users` — User listing (paginated)
- `GET /api/audit-log` — Audit log viewer

### API
- `POST /api/validate-url` — Validate a URL against allowlist
- `GET /api/fetch-data?resource=` — Fetch data by whitelisted resource type
- `GET /api/search?q=&type=` — Search content

## Architecture

- `server.js` — Entry point
- `app/app.js` — Express application and route definitions
- `app/middleware.js` — Request URL processing and access control middleware
- `app/services/userService.js` — User and content business logic
- `app/services/auditService.js` — In-memory audit logging
- `app/views/` — EJS templates
- `app/public/style.css` — Stylesheet

## Development

```bash
npm install --save-dev nodemon
npm run dev
```