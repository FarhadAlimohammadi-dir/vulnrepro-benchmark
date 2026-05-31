# CRM Community Portal

A lightweight Salesforce Lightning-style CRM portal for support communities.

## Features

- User login and session management with role-based access
- Query CRM objects (User, Case, Account, Contact) via Aura-compatible API
- Public article knowledge base with keyword search
- Support case submission and tracking
- Audit log for admin users
- User preference settings (display name, timezone, language)

## Quick Start

```bash
docker-compose up --build
```

Access at `http://localhost:9000`

### Demo Credentials

| Username | Password | Role  |
|----------|----------|-------|
| alice    | pass123  | admin |
| bob      | pass456  | agent |
| guest    | guest    | guest |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/` | No | Home / login page |
| POST | `/login` | No | Authenticate |
| GET  | `/logout` | No | End session |
| GET  | `/dashboard` | Yes | Main dashboard |
| GET  | `/dashboard/cases` | Yes | Case list |
| GET  | `/dashboard/settings` | Yes | User preferences |
| POST | `/dashboard/settings` | Yes | Save preferences |
| GET  | `/api/health` | No | Health check |
| GET  | `/api/public/articles` | No | Public KB articles |
| GET  | `/api/cases/public` | No | Public case listing |
| GET  | `/api/search?q=` | No | Keyword search |
| POST | `/api/validate-email` | No | Email format check |
| GET  | `/api/audit-log` | Admin | Recent audit events |
| GET  | `/api/profile` | Yes | Current user profile |
| POST | `/api/aura` | No | Aura data API |

## Aura API Actions

```json
{ "action": "getObjects", "params": {} }
{ "action": "queryObject", "params": { "objectName": "users", "fields": ["username","email"] } }
{ "action": "updateRecord", "params": { "objectName": "cases", "recordId": 1, "fields": { "status": "closed" } } }
```

## Database Schema

| Table | Key Columns |
|-------|-------------|
| users | id, username, email, ssn, phone |
| cases | id, subject, description, status, owner_id, created_at, public |
| accounts | id, name, industry, revenue, internal_notes |
| articles | id, title, body, author_id, public |
| contacts | id, name, email, account_id, phone |
| audit_log | id, actor, action, target, ts |
| user_prefs | user_id, displayName, timezone, language |

## Architecture

- **Runtime:** Node.js 20
- **Framework:** Express 4
- **Database:** SQLite via better-sqlite3
- **Templates:** EJS
- **Sessions:** express-session (in-memory)