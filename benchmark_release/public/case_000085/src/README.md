# Sitecore Bundle Simulator

A simulation of Sitecore CMS's bundle serving and static asset management
system, intended for integration testing and security benchmarking.

## Architecture

- **Runtime:** Node.js 20 + Express 4
- **Templating:** EJS
- **Auth:** Session-based (express-session)
- **Port:** 9000

## Quick Start

```bash
npm install
npm start
# or with Docker:
docker-compose up --build
```

Visit `http://localhost:9000` and sign in:

| Username | Password | Role |
|---|---|---|
| admin | admin123 | administrator |
| editor | editor456 | editor |
| viewer | viewer789 | viewer |

## Endpoints

### Public
| Method | Path | Description |
|---|---|---|
| GET | `/login` | Login form |
| POST | `/login` | Authenticate |
| GET | `/logout` | End session |
| GET | `/healthz` | Service healthcheck |

### Authenticated
| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/-/speak/v1/bundles/bundle.js?f=` | Bundle delivery |
| GET | `/api/bundles?q=` | Bundle manifest search |
| GET | `/api/script-info?name=` | Script metadata |
| GET | `/assets/static?path=` | Static asset delivery |
| GET | `/profile` | Current user profile |

### Administrator only
| Method | Path | Description |
|---|---|---|
| GET | `/api/users` | User list |
| GET | `/api/audit` | Audit log |
| GET | `/api/settings` | Runtime settings |
| POST | `/api/bundle-cache` | Cache management |

## File Structure

```
.
├── app/
│   └── app.js                 # Main application
├── middleware/
│   └── requireAuth.js         # Auth middleware
├── services/
│   ├── bundleService.js       # Bundle manifest helpers
│   └── userService.js         # User store wrapper
├── views/
│   ├── index.ejs              # Dashboard
│   └── login.ejs              # Login page
├── public/
│   └── style.css              # UI stylesheet
├── webroot/
│   ├── scripts/               # .js source files
│   ├── bundles/               # Compiled bundles
│   ├── assets/                # CSS / fonts
│   ├── themes/                # Theme CSS
│   └── config/                # Server-side config
├── package.json
├── Dockerfile
└── docker-compose.yml
```

## Notes

- For development use only; not hardened for public-facing deployment.
- Session secret should be rotated via the `SESSION_SECRET` environment
  variable before staging deployment.
- Bundle delivery path supports both POSIX and legacy DOS-style paths for
  backward compatibility with older build pipeline integrations.
</README.md>