import sqlite3
import hashlib
import os
import logging
from datetime import datetime
from flask import g

logger = logging.getLogger('nexus.db')
DATABASE = os.environ.get('DB_PATH', '/tmp/nexus.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def _get_raw_conn():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_raw_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role         TEXT NOT NULL DEFAULT 'employee',
            display_name TEXT NOT NULL DEFAULT '',
            email        TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS documents (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT NOT NULL,
            body         TEXT NOT NULL,
            source       TEXT NOT NULL DEFAULT 'internal',
            tags         TEXT,
            uploaded_by  INTEGER,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            action     TEXT NOT NULL,
            user_id    INTEGER,
            detail     TEXT,
            ip_addr    TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS workspace_settings (
            id              INTEGER PRIMARY KEY DEFAULT 1,
            allow_external  INTEGER NOT NULL DEFAULT 1,
            max_doc_size    INTEGER NOT NULL DEFAULT 5000,
            retention_days  INTEGER NOT NULL DEFAULT 90,
            updated_at      TEXT
        );
    """)

    # ── Seed users ────────────────────────────────────────────────
    users = [
        ('alice',   'password123', 'admin',    'Alice Merritt',    'alice@nexus.internal'),
        ('bob',     'letmein',     'employee', 'Bob Tanaka',       'bob@nexus.internal'),
        ('carol',   'nexus2024',   'employee', 'Carol Okonkwo',    'carol@nexus.internal'),
        ('dave',    'dave2024',    'employee', 'Dave Lindqvist',   'dave@nexus.internal'),
        ('eve',     'eve@nexus1',  'viewer',   'Eve Sharma',       'eve@nexus.internal'),
        ('mallory', 'ml0rry99',    'viewer',   'Mallory Chen',     'mallory@nexus.internal'),
    ]
    for username, password, role, display_name, email in users:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        try:
            conn.execute(
                'INSERT INTO users (username, password_hash, role, display_name, email) VALUES (?,?,?,?,?)',
                (username, pw_hash, role, display_name, email)
            )
        except sqlite3.IntegrityError:
            pass

    # ── Seed documents ────────────────────────────────────────────
    docs = [
        (
            'Q4 2024 Budget Planning',
            'Engineering allocation for Q4: $4.2M approved by CFO on Oct 3. '
            'Headcount increase of 12 approved across Platform and ML teams. '
            'Cloud infrastructure ceiling raised to $800k/mo. Confidential — do not distribute.',
            'gmail', 'budget,finance,confidential', None
        ),
        (
            'Project Falcon — Acquisition Brief',
            'Planned acquisition of NovaCorp for $50M. Board approval pending Q1 2025. '
            'Integration lead: Alice Merritt. API credentials: NEXUS_INTERNAL_KEY=sk-live-9f2a8b3c. '
            'Confidential — board eyes only.',
            'docs', 'acquisition,strategy,confidential', None
        ),
        (
            'H1 2025 Salary Review Schedule',
            'Annual salary review for senior staff scheduled January 15–20. '
            'Compensation band updates attached. HR data — confidential.',
            'calendar', 'hr,salary,confidential', None
        ),
        (
            'Engineering Roadmap 2025',
            'Q1: Auth service refactor and SSO rollout. '
            'Q2: AI pipeline production release. '
            'Q3: Mobile SDK for iOS and Android. '
            'Q4: Enterprise tier with SLA guarantees.',
            'docs', 'roadmap,engineering', None
        ),
        (
            'All-Hands Meeting Notes — November 2024',
            'Company grew 40% YoY. Two new offices opening in Austin and London. '
            'Product demo scheduled for December 10. CEO highlighted AI assistant adoption at 78%.',
            'calendar', 'meeting,allhands', None
        ),
        (
            'Vendor Contract — CloudHost Inc',
            'Three-year contract signed Oct 2024. Annual spend: $1.2M. '
            'SLA: 99.95% uptime. Primary contact: James Ortega (james@cloudhost.com).',
            'docs', 'vendor,finance,contracts', None
        ),
        (
            'Security Policy v3.2',
            'All production credentials must rotate every 90 days. '
            'MFA required for admin accounts. Incident response SLA: 4 hours P1, 24 hours P2. '
            'Contact security@nexus.internal for exceptions.',
            'docs', 'security,policy', None
        ),
        (
            'Customer Success Report — Q3 2024',
            'NPS score: 72 (up from 61 in Q2). Churn rate: 2.1%. '
            'Top requested feature: bulk export. '
            '15 enterprise deals closed totalling $3.8M ARR.',
            'docs', 'customers,report,quarterly', None
        ),
        (
            'Onboarding Checklist — New Hires',
            'Day 1: IT setup, badge, GitHub access. '
            'Day 3: Meet your buddy. '
            'Week 1: Department overview sessions. '
            'Week 2: First PR merged. '
            'Month 1: 30-day check-in with manager.',
            'docs', 'hr,onboarding', None
        ),
        (
            'Data Retention Policy',
            'Customer PII: 3 years post-contract. '
            'Internal comms: 7 years. '
            'Audit logs: 5 years. '
            'Backups destroyed within 30 days of contract end per GDPR Art. 17.',
            'docs', 'policy,compliance,gdpr', None
        ),
        (
            'Team OKRs — Q4 2024',
            'Objective 1: Ship AI assistant GA — KR1 95% uptime, KR2 <2s p95 latency. '
            'Objective 2: Grow enterprise pipeline — KR1 20 qualified leads, KR2 5 POCs. '
            'Objective 3: Improve eng velocity — KR1 DORA elite tier.',
            'docs', 'okrs,planning', None
        ),
        (
            'Legal Holds Notice — Oct 2024',
            'All materials relating to patent case #2024-7721 must be preserved. '
            'Do not delete any emails or documents tagged "falcon" or "novacorp". '
            'Contact legal@nexus.internal immediately if served with subpoena.',
            'gmail', 'legal,confidential', None
        ),
        (
            'Infrastructure Incident Report — INC-0421',
            'Date: 2024-10-18. Duration: 47 minutes. Impact: 12% of API traffic. '
            'Root cause: misconfigured load balancer rule after routine certificate rotation. '
            'Action items: add cert-rotation runbook, gate on automated health check.',
            'docs', 'incident,engineering,infra', None
        ),
        (
            'Marketing Campaign — Winter 2024',
            'Budget: $180k. Channels: LinkedIn (40%), SEM (35%), Events (25%). '
            'Goal: 500 MQLs. Landing page live Dec 1. '
            'A/B test variant B shows 22% higher conversion in staging.',
            'docs', 'marketing,campaign', None
        ),
        (
            'Partner Integration Guide',
            'Webhook format: JSON POST to /api/ingest. Auth: Bearer token in header. '
            'Supported sources: gmail, calendar, docs, external, shared. '
            'Rate limit: 100 req/min per partner. Contact integrations@nexus.internal.',
            'docs', 'integration,api,partner', None
        ),
    ]
    for title, body, source, tags, uploaded_by in docs:
        try:
            conn.execute(
                'INSERT INTO documents (title, body, source, tags, uploaded_by) VALUES (?,?,?,?,?)',
                (title, body, source, tags, uploaded_by)
            )
        except Exception:
            pass

    # ── Seed workspace settings ───────────────────────────────────
    try:
        conn.execute('INSERT OR IGNORE INTO workspace_settings (id) VALUES (1)')
    except Exception:
        pass

    conn.commit()
    conn.close()
    logger.info('Database initialized')