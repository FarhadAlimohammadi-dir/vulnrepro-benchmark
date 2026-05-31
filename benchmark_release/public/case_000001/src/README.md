# NexusRelay

NexusRelay is an AI workflow automation platform that connects your agents
to enterprise data sources through a unified relay gateway. Define multi-step
workflows, register plugins from the marketplace, and receive real-time
webhook notifications when tasks complete.

## Features

- **Workflow Studio** — Create, edit, schedule, and monitor automated workflows
- **Gateway Routing** — Route agent traffic through your preferred relay endpoint
- **Plugin Marketplace** — Extend agent capabilities with vetted plugins
- **Webhook Notifications** — Push workflow events to any HTTPS endpoint
- **Exec Approvals** — Require confirmation before agents run shell commands
- **Audit Log** — Full audit trail of all platform actions
- **Admin Panel** — User management and system health overview

## Quick Start

```bash
docker compose up --build
```

Open http://localhost:9000 and sign in:

| Username | Password   | Role     |
|----------|------------|----------|
| alice    | hunter2    | admin    |
| bob      | relay123   | user     |
| carol    | workflow!  | user     |
| dave     | gateway99  | user     |
| eve      | nexus2024  | operator |

## Configuration

| Variable         | Default              | Description                  |
|------------------|----------------------|------------------------------|
| `PORT`           | `9000`               | HTTP listen port             |
| `SESSION_SECRET` | dev value            | Session signing secret       |
| `DB_PATH`        | `./nexusrelay.db`    | SQLite database path         |

## API Reference

### Agent API (requires `x-nexus-token` header)

| Method | Path                     | Description                         |
|--------|--------------------------|-------------------------------------|
| GET    | `/api/agent/token-info`  | Token metadata and scopes           |
| GET    | `/api/agent/status`      | Runtime status                      |
| POST   | `/api/agent/exec-policy` | Toggle approval gates and sandbox   |
| POST   | `/api/agent/run`         | Execute a shell command             |

### Workspace

| Method | Path               | Description                                      |
|--------|--------------------|--------------------------------------------------|
| GET    | `/workspace/load`  | Load workspace; `gatewayUrl` query param applies endpoint override |

## License

MIT