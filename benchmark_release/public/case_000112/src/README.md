# TaskFlow — Project & Task Management

TaskFlow is an internal project management tool for engineering teams.
It supports projects, tasks, comments, and team notifications.

## Features

- **Projects**: Create and manage projects, invite team members
- **Tasks**: Create tasks with priority levels, assignees, and due dates
- **Comments**: Collaborate on tasks with threaded comments
- **Notifications**: Get notified when tasks are assigned to you
- **Search**: Find tasks across your projects

## Getting Started

```bash
docker-compose up --build
```

The app will be available at http://localhost:9000

## Default Accounts

| Username | Password       | Role   |
|----------|----------------|--------|
| alice    | AlicePass123!  | admin  |
| bob      | BobPass123!    | member |
| charlie  | CharliePass123!| member |

## Tech Stack

- Python 3.12 / Flask
- SQLite (persistent via Docker volume)
- Flask-Login for session management
- bcrypt for password hashing

## Development

```bash
pip install -r requirements.txt
python app.py
```

## Architecture

```
app.py              # Application entry point
db.py               # Database initialization and seeding
models/user.py      # User model for Flask-Login
routes/
  auth.py           # Login/logout
  tasks.py          # Task CRUD, comments, search
  projects.py       # Project management
  notifications.py  # Notification center
  profile.py        # User profile management
templates/          # Jinja2 HTML templates
```