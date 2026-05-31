"""
Database seeding script. Run once at container startup.
Populates default users, sample articles, and audit log entries.
"""

import os
import sys
import sqlite3
import bcrypt
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE = os.environ.get('DATABASE_PATH', '/app/data/contentflow.db')


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def seed():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'viewer',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            last_login  TEXT
        );

        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            slug        TEXT UNIQUE NOT NULL,
            body        TEXT NOT NULL,
            author      TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'general',
            tags        TEXT,
            status      TEXT NOT NULL DEFAULT 'draft',
            published_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT NOT NULL,
            username    TEXT,
            ip_address  TEXT,
            details     TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    # Seed users
    users = [
        ('alice', 'alice@contentflow.io', hash_pw('AlicePass123!'), 'admin'),
        ('bob',   'bob@contentflow.io',   hash_pw('BobPass123!'),   'editor'),
        ('charlie', 'charlie@contentflow.io', hash_pw('CharliePass123!'), 'viewer'),
        ('diana', 'diana@contentflow.io', hash_pw('Diana#2024'),    'editor'),
        ('evan',  'evan@contentflow.io',  hash_pw('Ev4nSecure!'),   'viewer'),
        ('fiona', 'fiona@contentflow.io', hash_pw('F!ona2025'),     'viewer'),
    ]

    for u in users:
        try:
            conn.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
                u
            )
            logger.info("Seeded user: %s", u[0])
        except sqlite3.IntegrityError:
            logger.debug("User already exists: %s", u[0])

    # Seed articles
    articles = [
        ('Getting Started with ContentFlow', 'getting-started',
         'ContentFlow is a modern headless CMS built for scale. This guide walks you through the initial setup.',
         'alice', 'guides', 'cms,setup,beginner', 'published', '2025-01-10 09:00:00'),

        ('Understanding Content Nodes', 'understanding-content-nodes',
         'Content in ContentFlow is organised as a tree of nodes. Each node has a type, properties, and children.',
         'alice', 'architecture', 'cms,nodes,architecture', 'published', '2025-01-15 10:30:00'),

        ('API Reference: Articles Endpoint', 'api-reference-articles',
         'The /api/v1/articles endpoint supports GET, POST, PUT, and DELETE operations.',
         'bob', 'api', 'api,reference,articles', 'published', '2025-01-20 14:00:00'),

        ('Configuring the Dispatcher Layer', 'configuring-dispatcher',
         'The dispatcher sits in front of your publish instances and filters requests based on configured rules.',
         'alice', 'operations', 'dispatcher,ops,security', 'published', '2025-02-01 08:00:00'),

        ('Search Integration Guide', 'search-integration',
         'ContentFlow supports full-text search out of the box via the /api/v1/search endpoint.',
         'bob', 'guides', 'search,integration', 'published', '2025-02-10 11:00:00'),

        ('Multi-environment Deployments', 'multi-environment-deployments',
         'Best practices for deploying ContentFlow across development, staging, and production environments.',
         'diana', 'operations', 'devops,deployment', 'published', '2025-02-15 09:30:00'),

        ('Content Replication Deep Dive', 'content-replication',
         'Author instances push content to publish instances via the replication queue.',
         'alice', 'architecture', 'replication,architecture', 'published', '2025-02-20 16:00:00'),

        ('Managing User Roles', 'managing-user-roles',
         'ContentFlow supports three built-in roles: admin, editor, and viewer.',
         'alice', 'administration', 'users,roles,admin', 'published', '2025-03-01 10:00:00'),

        ('CDN Integration', 'cdn-integration',
         'Integrate ContentFlow with major CDN providers to cache static assets at the edge.',
         'bob', 'operations', 'cdn,performance,caching', 'published', '2025-03-10 13:00:00'),

        ('Custom Dispatcher Rules', 'custom-dispatcher-rules',
         'Learn how to write custom dispatcher filter rules to match your security requirements.',
         'diana', 'operations', 'dispatcher,security,rules', 'published', '2025-03-15 15:00:00'),

        ('GraphQL Support Preview', 'graphql-support-preview',
         'ContentFlow 5.0 will ship with native GraphQL support. Here is an early preview.',
         'alice', 'product', 'graphql,preview,v5', 'draft', '2025-03-20 09:00:00'),

        ('Webhook Configuration', 'webhook-configuration',
         'Outbound webhooks let you trigger downstream pipelines when content is published.',
         'bob', 'api', 'webhooks,integration', 'published', '2025-03-25 11:30:00'),

        ('Audit Log Best Practices', 'audit-log-best-practices',
         'Retain audit logs for at least 90 days and ship them to a SIEM for alerting.',
         'alice', 'administration', 'audit,compliance,logs', 'published', '2025-04-01 08:00:00'),

        ('Performance Tuning Guide', 'performance-tuning',
         'Tips for tuning ContentFlow for high-traffic workloads.',
         'evan', 'guides', 'performance,tuning', 'published', '2025-04-05 14:00:00'),

        ('Scheduled Publishing', 'scheduled-publishing',
         'Use the scheduled publishing feature to queue articles for future release.',
         'diana', 'guides', 'scheduling,publishing', 'published', '2025-04-10 10:00:00'),
    ]

    for a in articles:
        try:
            conn.execute(
                "INSERT INTO articles "
                "(title, slug, body, author, category, tags, status, published_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                a
            )
            logger.info("Seeded article: %s", a[0])
        except sqlite3.IntegrityError:
            logger.debug("Article already exists: %s", a[0])

    # Seed audit log
    audit_entries = [
        ('login', 'alice', '10.0.1.5', 'Successful login'),
        ('article_publish', 'alice', '10.0.1.5', 'Published article: getting-started'),
        ('login', 'bob', '10.0.1.12', 'Successful login'),
        ('article_update', 'bob', '10.0.1.12', 'Updated article: api-reference-articles'),
        ('login_fail', 'unknown', '198.51.100.7', 'Failed login attempt'),
        ('config_view', 'alice', '10.0.1.5', 'Viewed system configuration'),
        ('user_create', 'alice', '10.0.1.5', 'Created user: diana'),
        ('article_draft', 'diana', '10.0.1.20', 'Saved draft: graphql-support-preview'),
    ]

    for e in audit_entries:
        try:
            conn.execute(
                "INSERT INTO audit_log (event_type, username, ip_address, details) "
                "VALUES (?,?,?,?)",
                e
            )
        except Exception as ex:
            logger.warning("Audit seed error: %s", ex)

    conn.commit()
    conn.close()
    logger.info("Seeding complete.")


if __name__ == '__main__':
    seed()