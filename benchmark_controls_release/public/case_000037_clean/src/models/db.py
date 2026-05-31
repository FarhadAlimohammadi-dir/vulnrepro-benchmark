import sqlite3
import os
import hashlib
import bcrypt
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', './data/docmanager.db')


def get_db():
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    db = get_db()
    cursor = db.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            plan TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            display_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            tenant_id TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            visibility TEXT DEFAULT 'private',
            classification TEXT DEFAULT 'internal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS document_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            shared_with_tenant TEXT NOT NULL,
            shared_by_user INTEGER NOT NULL,
            permissions TEXT DEFAULT 'read',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS integration_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id TEXT UNIQUE NOT NULL,
            issuing_tenant TEXT NOT NULL,
            target_tenant TEXT NOT NULL,
            actor_user TEXT NOT NULL,
            scope TEXT DEFAULT 'read',
            token_hash TEXT NOT NULL,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            is_revoked INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tenant_integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_tenant TEXT NOT NULL,
            target_tenant TEXT NOT NULL,
            integration_key TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Seed tenants
    tenants = [
        ('acme', 'Acme Corporation', 'enterprise'),
        ('globex', 'Globex Industries', 'professional'),
        ('initech', 'Initech Solutions', 'free'),
        ('umbrella', 'Umbrella Consulting', 'professional'),
    ]

    for t in tenants:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO tenants (tenant_id, name, plan) VALUES (?,?,?)",
                t
            )
        except sqlite3.IntegrityError:
            pass

    # Seed users with bcrypt hashed passwords
    def make_hash(pw):
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

    users = [
        ('alice', 'alice@acme.example.com', make_hash('AlicePass123!'), 'acme', 'admin', 'Alice Admin'),
        ('bob', 'bob@globex.example.com', make_hash('BobPass123!'), 'globex', 'member', 'Bob Member'),
        ('charlie', 'charlie@acme.example.com', make_hash('CharliePass123!'), 'acme', 'member', 'Charlie Dev'),
        ('diana', 'diana@globex.example.com', make_hash('Diana2024!'), 'globex', 'admin', 'Diana Manager'),
        ('eve', 'eve@initech.example.com', make_hash('Eve!nitech99'), 'initech', 'admin', 'Eve Director'),
        ('frank', 'frank@umbrella.example.com', make_hash('FrankPass!'), 'umbrella', 'member', 'Frank Analyst'),
        ('grace', 'grace@acme.example.com', make_hash('GraceAcme!7'), 'acme', 'member', 'Grace Engineer'),
        ('heidi', 'heidi@globex.example.com', make_hash('HeidiG!obex'), 'globex', 'member', 'Heidi Designer'),
    ]

    for u in users:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (username, email, password_hash, tenant_id, role, display_name) VALUES (?,?,?,?,?,?)",
                u
            )
        except sqlite3.IntegrityError:
            pass

    # Seed documents
    docs = [
        ('Q3 Financial Report', 'Confidential Q3 results...', 'acme', 1, 'private', 'confidential'),
        ('Product Roadmap 2025', 'Upcoming features and timelines...', 'acme', 1, 'internal', 'internal'),
        ('Engineering Runbook', 'Deployment procedures...', 'acme', 3, 'private', 'internal'),
        ('Sales Deck Q4', 'Customer presentations...', 'globex', 2, 'internal', 'internal'),
        ('Partnership Agreement', 'Terms with Acme Corp...', 'globex', 2, 'private', 'confidential'),
        ('HR Policy 2024', 'Employee guidelines...', 'initech', 5, 'private', 'internal'),
        ('Security Audit Results', 'Penetration test findings...', 'acme', 1, 'private', 'confidential'),
        ('API Documentation', 'Integration guide...', 'globex', 4, 'internal', 'public'),
        ('Budget Forecast', 'Annual projections...', 'umbrella', 6, 'private', 'confidential'),
        ('Team Charter', 'Mission and values...', 'acme', 7, 'internal', 'internal'),
        ('Vendor Contracts', 'Supplier agreements...', 'globex', 4, 'private', 'confidential'),
        ('Onboarding Guide', 'New employee materials...', 'initech', 5, 'internal', 'internal'),
    ]

    for d in docs:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO documents (title, content, tenant_id, owner_id, visibility, classification) VALUES (?,?,?,?,?,?)",
                d
            )
        except sqlite3.IntegrityError:
            pass

    # Seed tenant integrations (acme <-> globex have a cross-tenant integration)
    integrations = [
        ('globex', 'acme', 'intkey-globex-acme-abc123'),
        ('acme', 'globex', 'intkey-acme-globex-xyz789'),
    ]
    for i in integrations:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO tenant_integrations (source_tenant, target_tenant, integration_key) VALUES (?,?,?)",
                i
            )
        except sqlite3.IntegrityError:
            pass

    db.commit()
    db.close()
    logger.info("Database initialized and seeded")