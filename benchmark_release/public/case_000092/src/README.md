# Nexus Analytics

A business intelligence and analytics platform for managing reports, datasets,
and custom report templates.

## Features

- **Report Management**: Create, manage, and publish analytical reports
- **Dataset Integration**: Upload and manage data sources
- **Custom Templates**: Design custom HTML report layouts using Jinja2
- **Audit Logging**: Track all user actions for compliance
- **Role-Based Access**: Admin, Analyst, and Viewer roles

## Quick Start

```bash
docker-compose up --build
```

Access the platform at http://localhost:9000

## Default Accounts

| Username | Password         | Role    |
|----------|-----------------|---------|
| alice    | AlicePass123!   | admin   |
| bob      | BobPass123!     | analyst |
| charlie  | CharliePass123! | analyst |

## API Overview

### Authentication
- `POST /auth/login` — Obtain session
- `POST /auth/logout` — End session
- `GET /auth/me` — Current user info

### Reports
- `GET /reports/list` — List all reports
- `GET /reports/<id>` — Report details
- `POST /api/reports/template/save` — Save custom template
- `GET /reports/preview/<filename>` — Preview rendered template
- `POST /api/reports/export` — Export report data

### Datasets
- `GET /api/datasets` — List datasets
- `POST /api/datasets/upload` — Upload CSV data

### Administration
- `GET /api/users/search?q=` — Search users (admin)
- `GET /api/audit` — View audit logs

## Template System

Nexus Analytics supports custom Jinja2 report templates. Analysts can design
layouts using standard HTML and Jinja2 template syntax. Templates are stored
and can be previewed directly in the browser.

## Architecture

- **Backend**: Flask (Python 3.12)
- **Database**: SQLite3
- **Templates**: Jinja2
- **Auth**: Flask-Login with session cookies