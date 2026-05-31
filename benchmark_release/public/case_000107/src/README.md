# Notes App

A collaborative rich-text note-taking application built with Flask.

## Features

- Rich HTML notes with a live preview pane
- Public sharing via signed tokens
- Full-text search across your notes
- Admin audit log for compliance

## Quick Start

```bash
docker compose up --build
```

App available at http://localhost:9000

## Default Accounts

| Username | Password       | Role  |
|----------|---------------|-------|
| alice    | AlicePass123! | user  |
| bob      | BobPass123!   | user  |
| charlie  | CharliePass123! | user |
| admin    | Adm1nS3cur3!  | admin |

## Architecture

- **Flask** backend with SQLite storage
- **bleach** for HTML content cleaning
- **announce.js** — in-house notification widget loaded in preview panes
- Session-based authentication via Flask-Login

## Development

```bash
pip install -r requirements.txt
python app.py
```

## Note Content Format

Notes accept a subset of HTML. Allowed tags include headings, paragraphs,
lists, tables, links, and images. JavaScript is stripped by the content
cleaner.