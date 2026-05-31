# NexusAI Platform

NexusAI is a personal productivity assistant that connects your calendar,
contacts, notifications, messaging, and phone tools through a conversational
interface. Manage your day without switching between apps.

## Features

- **Conversational assistant** — natural language interface to all tools
- **Contacts CRUD** — manage your address book with search and pagination
- **Calendar** — create and review upcoming events
- **Notifications** — see real-time alerts from connected services
- **Phone integration** — hands-free calling via the assistant
- **SMS** — send messages with a built-in review/confirmation step
- **Admin panel** — user management, platform stats, and audit log
- **Profile page** — manage display name, email, and integration tokens

## Quick Start

```bash
docker compose up --build
```

Then open [http://localhost:9000](http://localhost:9000).

### Demo Accounts

| Username | Password  | Role  |
|----------|-----------|-------|
| alice    | alice123  | admin |
| bob      | bob123    | user  |
| carol    | carol123  | user  |
| dave     | dave123   | user  |
| eve      | eve123    | user  |

## Architecture

| Layer       | Technology                     |
|-------------|-------------------------------|
| Runtime     | Node.js 20                    |
| Framework   | Express 4                     |
| Templates   | EJS                           |
| Database    | SQLite via better-sqlite3     |
| Sessions    | express-session               |
| Logging     | morgan                        |

## Configuration

| Variable | Default        | Description             |
|----------|----------------|-------------------------|
| `PORT`   | `9000`         | HTTP listening port     |
| `DB_PATH`| `./nexus.db`   | SQLite database path    |

## Tool Reference

| Tool             | Auto-run | Description                          |
|------------------|----------|--------------------------------------|
| notifications    | ✓        | Read recent notification items       |
| phone            | ✓        | Place a call or DTMF sequence        |
| sms              | ✗        | Send SMS (confirmation required)     |
| calendar         | ✓        | Create calendar events               |
| contacts_search  | ✓        | Search contacts by name or phone     |

## Development

```bash
cd app
npm install
node app.js
```