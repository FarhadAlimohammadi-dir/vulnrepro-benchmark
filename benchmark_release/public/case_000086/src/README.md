# DocManager - Document Management System

A web-based document management and reporting platform for organizational use.

## Features

- Secure authentication with role-based access control
- Document upload, organization, and search
- Report template management and preview
- Comprehensive audit logging
- Admin dashboard with system statistics

## Getting Started

### Prerequisites
- Docker and Docker Compose

### Running the Application

```bash
docker-compose up --build
```

The application will be available at http://localhost:9000

### Default Accounts

| Username | Password       | Role    |
|----------|----------------|---------|
| alice    | AlicePass123!  | User    |
| bob      | BobPass123!    | User    |
| charlie  | CharliePass123!| Admin   |
| diana    | Diana2024!     | User    |
| evan     | EvanMgr99!     | Manager |

## API Reference

### Authentication
- `POST /auth/login` - Login with username/password
- `POST /auth/logout` - Logout current user
- `GET /auth/me` - Get current user info
- `POST /auth/change-password` - Change password

### Documents
- `GET /api/documents/list` - List all documents (paginated)
- `GET /api/documents/search?q=<term>` - Search documents
- `POST /api/documents/upload` - Upload a document
- `GET /api/documents/<id>/metadata` - Get document metadata

### Reports
- `GET /api/reports/list` - List available reports
- `GET /api/reports/<id>` - Get report by ID
- `GET /api/reports/preview?file=<filename>` - Preview report template
- `POST /api/reports/generate` - Queue report generation

### Admin (requires admin role)
- `GET /api/admin/users` - List all users
- `GET /api/admin/audit` - View audit logs
- `POST /api/admin/template` - Create report template
- `GET /api/admin/stats` - System statistics

## Architecture

- **Backend**: Python 3.12 + Flask
- **Database**: SQLite3
- **Authentication**: Flask-Login with session management
- **File Storage**: Local filesystem

## Development Notes

Report templates are stored in the `/app/reports/` directory. The preview
endpoint allows authorized users to view report HTML files by filename.