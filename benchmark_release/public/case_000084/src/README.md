# TemplateStudio

A web-based ad template management system with support for remote asset processing.

## Features

- **Template Management:** Create, edit, search, and organize HTML5 ad templates
- **Remote Asset Handling:** Automatically download and cache remote assets (images, videos) referenced in templates
- **Template Sharing:** Export and share template packages with team members
- **URL Validation:** Built-in URL validation for template metadata
- **Audit Logging:** Full action log for admin review
- **Role-Based Access:** Editor, viewer, and admin roles

## Installation

```bash
docker-compose up
```

Access the application at `http://localhost:9000`

**Demo Credentials:**
- Username: `demo`
- Password: `demo123`

**Admin Credentials:**
- Username: `admin`
- Password: `admin456`

## API Endpoints

### Authentication
- `POST /login` — User login
- `GET /logout` — Logout

### Template Management
- `POST /api/process-template` — Process template with remote assets
- `GET /api/templates/list` — List user templates
- `GET /api/templates/search?q=` — Search templates by name
- `POST /api/validate-urls` — Validate URLs in template metadata
- `GET /api/assets/preview?assetId=` — Preview asset file metadata
- `GET /api/asset-jobs/:templateId` — Check asset download job status

### User & System
- `GET /api/profile` — Current user profile
- `POST /api/profile/settings` — Update notification/timezone settings
- `GET /api/audit-log` — Audit log (admin only)
- `GET /health` — Service healthcheck

## Template JSON Format

```json
{
  "name": "Premium Ad Template",
  "remoteAssets": [
    "https://cdn.example.com/images/logo.png",
    "https://cdn.example.com/videos/promo.mp4"
  ]
}
```

## Directory Structure

```
/tmp/studio_templates/
  └── assets/
      ├── logo.png
      └── promo.mp4
```