# NexusAI Workspace

NexusAI Workspace is an enterprise AI assistant that lets your team search across the organization's documents, emails, and calendar events using natural language — powered by a retrieval-augmented generation (RAG) pipeline.

## Features

- **AI-Powered Assistant**: Natural-language queries against a live document corpus.
- **Multi-Source Indexing**: Ingest content from email, shared documents, calendar events, and partner integrations.
- **Document Library**: Browse, filter, and manage all indexed documents with pagination.
- **Admin Panel**: Manage users, change roles, and review the audit log.
- **Profile Pages**: Update display name and email; view personal activity.
- **Workspace Settings**: Configure retention, document size limits, and external ingestion.
- **Audit Logging**: Every significant action written to a tamper-evident audit table.

## Quick Start

```bash
docker-compose up --build
```

Open [http://localhost:9000](http://localhost:9000) in your browser.

### Default Accounts

| Username | Password    | Role     |
|----------|-------------|----------|
| alice    | password123 | admin    |
| bob      | letmein     | employee |
| carol    | nexus2024   | employee |
| dave     | dave2024    | employee |
| eve      | eve@nexus1  | viewer   |
| mallory  | ml0rry99    | viewer   |

## API Reference

| Method | Path                        | Auth     | Description                        |
|--------|-----------------------------|----------|------------------------------------|
| GET    | /api/assistant/query?q=     | Required | AI query with RAG retrieval        |
| POST   | /api/documents/share        | None     | Ingest externally shared artifact  |
| POST   | /api/documents/upload       | Required | Upload internal document           |
| GET    | /api/documents              | Required | Paginated document list            |
| GET    | /api/documents/:id          | Required | Single document detail             |
| PUT    | /api/documents/:id          | Required | Update document                    |
| GET    | /api/search/semantic?q=     | Required | Keyword search                     |
| POST   | /api/summarize              | Required | Summarize provided text            |
| GET    | /api/audit                  | Admin    | Retrieve audit log                 |
| GET    | /api/tags                   | Required | List all indexed tags              |

## Requirements

- Docker ≥ 20.10 and Docker Compose ≥ 1.29
- Port 9000 available on the host
</README.md>