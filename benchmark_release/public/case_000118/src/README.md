# Meridian HR Portal

Internal HR self-service portal for Meridian Corporation employees.

## Features

- Employee directory with search
- Leave request management
- Company announcements
- Profile management
- Audit logging (admin)

## Technology Stack

- Python 3.12 / Flask
- SQLite (persistent volume)
- AngularJS 1.1.3 (legacy frontend framework)

## Running with Docker

```bash
docker-compose up --build
```

Portal available at: http://localhost:9000

## Default Accounts

| Username  | Password         | Role     |
|-----------|-----------------|----------|
| alice     | AlicePass123!   | admin    |
| bob       | BobPass123!     | employee |
| charlie   | CharliePass123! | employee |

## Development Notes

- Database is initialized automatically on first run via `init_db.py`
- The AngularJS integration uses legacy 1.x for compatibility with existing
  form validation logic from the v1 portal migration
- Session management handled by Flask-Login
- All passwords are SHA-256 hashed with a random salt

## Support

Contact the IT Helpdesk at helpdesk@meridian.internal for access issues.