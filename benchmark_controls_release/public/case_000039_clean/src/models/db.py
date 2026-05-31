import sqlite3
import bcrypt
import logging
import os

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT DEFAULT 'free',
    owner_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS org_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER REFERENCES organizations(id),
    user_id INTEGER REFERENCES users(id),
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(org_id, user_id)
);

CREATE TABLE IF NOT EXISTS service_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER REFERENCES organizations(id),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    description TEXT,
    key_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER REFERENCES organizations(id),
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER REFERENCES organizations(id),
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def init_db(db_path: str):
    conn = get_db(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _seed_data(conn)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()


def _seed_data(conn):
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    logger.info("Seeding initial data...")

    users = [
        ('alice', 'alice@acme-corp.io', hash_password('AlicePass123!'), 'Alice Chen'),
        ('bob', 'bob@secret-startup.io', hash_password('BobPass123!'), 'Bob Martinez'),
        ('charlie', 'charlie@enterprise-co.io', hash_password('CharliePass123!'), 'Charlie Nguyen'),
        ('diana', 'diana@acme-corp.io', hash_password('DianaPass456!'), 'Diana Kumar'),
        ('eve', 'eve@secret-startup.io', hash_password('EvePass789!'), 'Eve Okonkwo'),
        ('frank', 'frank@acme-corp.io', hash_password('FrankPass321!'), 'Frank Russo'),
        ('grace', 'grace@enterprise-co.io', hash_password('GracePass654!'), 'Grace Tan'),
        ('henry', 'henry@secret-startup.io', hash_password('HenryPass987!'), 'Henry Patel'),
        ('iris', 'iris@acme-corp.io', hash_password('IrisPass111!'), 'Iris Johansson'),
        ('jack', 'jack@enterprise-co.io', hash_password('JackPass222!'), 'Jack Williams'),
    ]
    conn.executemany(
        "INSERT INTO users (username, email, password_hash, display_name) VALUES (?, ?, ?, ?)",
        users
    )
    conn.commit()

    orgs = [
        ('Acme Corp', 'acme-corp', 'enterprise', 1),
        ('Secret Startup', 'secret-startup', 'pro', 2),
        ('Enterprise Co', 'enterprise-co', 'enterprise', 3),
    ]
    conn.executemany(
        "INSERT INTO organizations (name, slug, plan, owner_id) VALUES (?, ?, ?, ?)",
        orgs
    )
    conn.commit()

    # org_id 1 = Acme Corp: alice(1), diana(4), frank(6), iris(9)
    # org_id 2 = Secret Startup: bob(2), eve(5), henry(8)
    # org_id 3 = Enterprise Co: charlie(3), grace(7), jack(10)
    members = [
        (1, 1, 'admin'), (1, 4, 'member'), (1, 6, 'member'), (1, 9, 'member'),
        (2, 2, 'admin'), (2, 5, 'member'), (2, 8, 'member'),
        (3, 3, 'admin'), (3, 7, 'member'), (3, 10, 'member'),
    ]
    conn.executemany(
        "INSERT INTO org_members (org_id, user_id, role) VALUES (?, ?, ?)",
        members
    )
    conn.commit()

    # Service accounts per org
    svc_accounts = [
        (1, 'ci-deployer', 'ci-deployer@acme-corp.iam.workspaceaccount.com', 'CI/CD deployment account'),
        (1, 'data-pipeline', 'data-pipeline@acme-corp.iam.workspaceaccount.com', 'ETL pipeline service'),
        (1, 'monitoring-agent', 'monitoring-agent@acme-corp.iam.workspaceaccount.com', 'Uptime monitor'),
        (2, 'prod-deployer', 'prod-deployer@secret-startup.iam.workspaceaccount.com', 'Production deployment'),
        (2, 'backup-service', 'backup-service@secret-startup.iam.workspaceaccount.com', 'Daily backup runner'),
        (2, 'analytics-bot', 'analytics-bot@secret-startup.iam.workspaceaccount.com', 'Analytics aggregator'),
        (2, 'secret-ml-trainer', 'ml-trainer@secret-startup.iam.workspaceaccount.com', 'Proprietary ML training'),
        (3, 'infra-manager', 'infra-manager@enterprise-co.iam.workspaceaccount.com', 'Infrastructure automation'),
        (3, 'audit-collector', 'audit-collector@enterprise-co.iam.workspaceaccount.com', 'Compliance audit collector'),
    ]
    conn.executemany(
        "INSERT INTO service_accounts (org_id, name, email, description) VALUES (?, ?, ?, ?)",
        svc_accounts
    )
    conn.commit()

    projects = [
        (1, 'Frontend App', 'frontend-app', 'Main customer-facing application'),
        (1, 'Data Platform', 'data-platform', 'Internal analytics and reporting'),
        (2, 'Core API', 'core-api', 'Primary API service'),
        (2, 'Mobile Backend', 'mobile-backend', 'Backend for mobile clients'),
        (3, 'Enterprise Suite', 'enterprise-suite', 'Main enterprise product'),
    ]
    conn.executemany(
        "INSERT INTO projects (org_id, name, slug, description) VALUES (?, ?, ?, ?)",
        projects
    )
    conn.commit()

    audit_entries = [
        (1, 1, 'member.invite', 'user', '4', '10.0.0.1'),
        (1, 1, 'project.create', 'project', '1', '10.0.0.1'),
        (2, 2, 'service_account.create', 'service_account', '4', '10.0.0.2'),
        (2, 2, 'project.create', 'project', '3', '10.0.0.2'),
        (3, 3, 'member.invite', 'user', '10', '10.0.0.3'),
    ]
    conn.executemany(
        "INSERT INTO audit_logs (org_id, user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
        audit_entries
    )
    conn.commit()
    logger.info("Seed data inserted successfully")