# PresetHub

A modern theme and configuration preset management platform for web applications.

## Features
- **Cloud Preset Storage:** Save and manage multiple theme configurations
- **Theme Customization:** Customize colors, typography, and UI settings
- **Preset Gallery:** Browse and discover community presets
- **Multi-User Support:** Secure per-user preset management
- **Live Preview:** Real-time theme preview as you configure
- **Audit Logging:** Track all configuration changes over time
- **Role-Based Access:** Admin, designer, and user roles supported

## Tech Stack
- **Backend:** Node.js + Express.js
- **Database:** SQLite with better-sqlite3
- **Frontend:** HTML + EJS templates + custom CSS
- **Authentication:** Session-based with secure cookies

## Getting Started

### Quick Start
```bash
docker-compose up
```

The application will be available at `http://localhost:9000`

### Manual Setup
```bash
cd app
npm install
npm start
```

### Default Credentials
- Username: `admin` | Password: `admin123`
- Username: `alice` | Password: `pass456`
- Username: `bob` | Password: `secret789`
- Username: `carol` | Password: `carol2024`
- Username: `dave` | Password: `dave2024`

## API Endpoints

### Authentication
- `POST /login` — Login with username and password
- `GET /logout` — Logout current session

### Presets
- `POST /api/presets/apply` — Apply a new preset configuration
- `GET /api/presets/list` — List all user presets (paginated)
- `POST /api/export-config` — Export preset as JSON
- `GET /api/presets/gallery` — Browse public preset gallery

### Configuration
- `POST /api/validate-preset` — Validate preset structure
- `POST /api/settings/update` — Update user display settings
- `GET /api/health` — System health status

### Discovery
- `GET /api/tags` — List all available tags
- `GET /api/search?q=term` — Search your presets
- `GET /api/users/:username/profile` — View a user profile
- `GET /api/admin/audit-log` — Admin: view audit log

## Example Preset
```json
{
  "name": "Dark Mode",
  "theme": {
    "dark": true,
    "colors": {
      "primary": "#bb86fc",
      "secondary": "#03dac6",
      "accent": "#ff0000"
    }
  },
  "icons": {
    "iconfont": "mdi"
  }
}
```

## License
MIT License — See LICENSE file for details
</README.md>