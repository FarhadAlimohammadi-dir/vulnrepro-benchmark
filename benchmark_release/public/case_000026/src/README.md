# CloudLens IAM Analyzer

CloudLens is a production-grade web dashboard for analyzing, visualizing, and auditing cloud IAM configurations across AWS-style environments. It provides real-time policy evaluation, access simulation, and a comprehensive audit trail.

## Features

- **Dashboard**: At-a-glance view of your IAM policies and resource access status
- **Policy Management**: Attach and detach inline IAM policies via REST API or UI
- **Permission Simulation**: Evaluate whether a user can perform a given action on a resource
- **Access Simulation**: Trace multi-hop access paths between identities and resources
- **Resource Browser**: Browse and access cloud resources based on IAM permissions
- **Audit Log**: Paginated, filterable audit trail of all platform actions
- **Admin Panel**: User management, account lifecycle, and system overview
- **Profile Page**: Per-user permission summary, notification inbox, and activity history
- **Notification System**: In-app alerts for policy changes and account events

## Quick Start

```bash
docker-compose up --build
```

Then open [http://localhost:9000](http://localhost:9000)

## Demo Accounts

| Username   | Password      | Role      | Department               |
|------------|---------------|-----------|--------------------------|
| admin      | Admin1234!    | admin     | Platform Engineering     |
| dev1       | Dev1pass!     | developer | Application Development  |
| dev2       | Dev2pass!     | developer | Application Development  |
| analyst    | Analyst99!    | analyst   | Security Operations      |
| analyst2   | Analyst2!     | analyst   | Business Intelligence    |
| readonly   | Readonly1!    | readonly  | Compliance               |
| sre1       | SRE1pass!     | developer | Site Reliability         |
| dataeng1   | DataEng1!     | developer | Data Engineering         |
| mlops1     | MLOps1pass!   | developer | ML Platform              |
| secops1    | SecOps1!      | analyst   | Security Operations      |

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Dashboard |
| GET/POST | /login | Authentication |
| POST | /logout | End session |
| GET | /iam/users | List all users (requires iam:ListUsers) |
| GET | /iam/user/:username | Detailed user policy view |
| POST | /iam/attach-policy | Attach inline policy to a user |
| POST | /iam/detach-policy | Remove an inline policy |
| POST | /iam/audit-policy | Evaluate hypothetical permission |
| GET | /iam/simulate | Simulate access path |
| GET | /iam/policy-report | Full org policy report (admin) |
| GET | /resources | List accessible resources |
| GET | /resources/search | Search resources |
| GET | /resources/:arn | Fetch resource data |
| GET | /profile | User profile and settings |
| POST | /profile/update | Update profile fields |
| GET | /admin | Admin overview |
| GET | /admin/audit | Paginated audit log |
| GET | /admin/users | User management |
| POST | /admin/users/create | Create user |
| POST | /admin/users/deactivate | Deactivate user |

## Architecture

- **Runtime**: Node.js 20 + Express 4
- **Templates**: EJS with shared partials
- **Database**: SQLite via better-sqlite3
- **Session**: express-session (server-side)
- **Logging**: morgan (HTTP) + custom audit service