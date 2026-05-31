import sqlite3
import os
import bcrypt
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///taskflow.db').replace('sqlite:///', '')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    """Initialize database schema and seed data."""
    conn = get_db()
    cursor = conn.cursor()

    # Create tables
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            department TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            project_id INTEGER NOT NULL,
            assignee_id INTEGER,
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            due_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            label TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            last_used DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')

    # Seed users if not present
    existing = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if existing == 0:
        users_seed = [
            ('alice', 'alice@taskflow.io', 'AlicePass123!', 'member', 'Engineering'),
            ('bob', 'bob@taskflow.io', 'BobPass123!', 'member', 'Design'),
            ('charlie', 'charlie@taskflow.io', 'CharliePass123!', 'admin', 'Operations'),
            ('diana', 'diana@taskflow.io', 'DianaPass456!', 'member', 'Marketing'),
            ('eve', 'eve@taskflow.io', 'EvePass789!', 'member', 'Engineering'),
            ('frank', 'frank@taskflow.io', 'FrankPass321!', 'member', 'Sales'),
            ('grace', 'grace@taskflow.io', 'GracePass654!', 'member', 'Engineering'),
            ('henry', 'henry@taskflow.io', 'HenryPass987!', 'member', 'HR'),
            ('iris', 'iris@taskflow.io', 'IrisPass111!', 'member', 'Finance'),
            ('jack', 'jack@taskflow.io', 'JackPass222!', 'member', 'Engineering'),
        ]

        for username, email, password, role, dept in users_seed:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cursor.execute(
                'INSERT INTO users (username, email, password_hash, role, department) VALUES (?, ?, ?, ?, ?)',
                (username, email, pw_hash, role, dept)
            )

        # Seed projects
        projects_seed = [
            ('TaskFlow v2 Launch', 'Main product launch for Q2', 1, 'active'),
            ('Mobile App Redesign', 'Complete UI overhaul for iOS and Android', 2, 'active'),
            ('API Gateway Migration', 'Move from monolith to microservices', 1, 'active'),
            ('Marketing Campaign Q3', 'Summer promotional campaign', 4, 'active'),
            ('Database Optimization', 'Index tuning and query performance', 5, 'completed'),
            ('HR Portal Upgrade', 'New self-service HR system', 8, 'active'),
            ('Sales Dashboard', 'Real-time metrics for sales team', 6, 'paused'),
            ('Security Audit 2024', 'Annual security review', 3, 'active'),
        ]

        for name, desc, owner_id, status in projects_seed:
            cursor.execute(
                'INSERT INTO projects (name, description, owner_id, status) VALUES (?, ?, ?, ?)',
                (name, desc, owner_id, status)
            )

        # Seed tasks
        tasks_seed = [
            ('Design system components', 'Build reusable UI library', 1, 2, 'in_progress', 'high', '2024-06-15'),
            ('Auth service refactor', 'Upgrade JWT implementation', 3, 5, 'todo', 'high', '2024-06-20'),
            ('Write API documentation', 'OpenAPI 3.0 specs', 1, 1, 'in_progress', 'medium', '2024-06-10'),
            ('Setup CI/CD pipeline', 'GitHub Actions workflows', 1, 5, 'completed', 'high', '2024-05-30'),
            ('Logo refresh', 'Update brand guidelines', 2, 2, 'todo', 'medium', '2024-07-01'),
            ('Performance testing', 'Load test with 10k concurrent', 3, 1, 'todo', 'critical', '2024-06-25'),
            ('Q3 email templates', 'Design 5 campaign emails', 4, 4, 'in_progress', 'medium', '2024-06-18'),
            ('Add query caching', 'Redis layer for hot queries', 5, 10, 'completed', 'high', '2024-05-20'),
            ('Onboarding flow', 'New employee portal wizard', 6, 8, 'in_progress', 'medium', '2024-07-15'),
            ('Pipeline integrations', 'Salesforce and HubSpot sync', 7, 6, 'todo', 'low', '2024-08-01'),
            ('Penetration test report', 'Review vendor findings', 8, 3, 'in_progress', 'critical', '2024-06-12'),
            ('Mobile push notifications', 'FCM and APNS integration', 2, 7, 'todo', 'medium', '2024-07-30'),
            ('Database backup scripts', 'Automated nightly backups', 5, 9, 'completed', 'high', '2024-05-15'),
            ('Rate limiting', 'Implement per-user API throttle', 3, 1, 'in_progress', 'high', '2024-06-22'),
            ('Accessibility audit', 'WCAG 2.1 AA compliance', 2, 2, 'todo', 'medium', '2024-07-10'),
        ]

        for title, desc, proj_id, assignee, status, priority, due in tasks_seed:
            cursor.execute(
                '''INSERT INTO tasks (title, description, project_id, assignee_id, status, priority, due_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (title, desc, proj_id, assignee, status, priority, due)
            )

        logger.info("Database seeded with initial data")

    conn.commit()
    conn.close()