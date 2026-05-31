import sqlite3
import bcrypt
import logging

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    bio TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'contributor',
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    project_id INTEGER NOT NULL,
    assignee_id INTEGER,
    creator_id INTEGER NOT NULL,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    due_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (assignee_id) REFERENCES users(id),
    FOREIGN KEY (creator_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def seed_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check if already seeded
    existing = conn.execute('SELECT COUNT(*) as c FROM users').fetchone()
    if existing['c'] > 0:
        conn.close()
        return

    logger.info("Seeding initial data...")

    # Seed users
    users = [
        ('alice', 'alice@corp.example.com', hash_password('AlicePass123!'), 'admin'),
        ('bob', 'bob@corp.example.com', hash_password('BobPass123!'), 'member'),
        ('charlie', 'charlie@corp.example.com', hash_password('CharliePass123!'), 'member'),
        ('diana', 'diana@corp.example.com', hash_password('DianaPass456!'), 'member'),
        ('eve', 'eve@corp.example.com', hash_password('EvePass456!'), 'member'),
    ]
    conn.executemany(
        'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
        users
    )

    # Seed projects
    projects = [
        ('Backend API Rewrite', 'Migrate legacy PHP API to Python/Flask', 1, 'active'),
        ('Mobile App v2', 'New React Native mobile application', 1, 'active'),
        ('Data Pipeline', 'ETL pipeline for analytics team', 2, 'active'),
        ('Customer Portal', 'Self-service portal for enterprise clients', 3, 'planning'),
        ('DevOps Tooling', 'Internal CI/CD improvements', 1, 'active'),
    ]
    conn.executemany(
        'INSERT INTO projects (name, description, owner_id, status) VALUES (?, ?, ?, ?)',
        projects
    )

    # Seed project members
    members = [
        (1, 1, 'owner'), (1, 2, 'contributor'), (1, 3, 'contributor'),
        (2, 1, 'owner'), (2, 4, 'contributor'),
        (3, 2, 'owner'), (3, 3, 'contributor'), (3, 5, 'contributor'),
        (4, 3, 'owner'), (4, 4, 'contributor'),
        (5, 1, 'owner'), (5, 2, 'contributor'), (5, 5, 'contributor'),
    ]
    conn.executemany(
        'INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)',
        members
    )

    # Seed tasks
    tasks = [
        ('Set up Flask project structure', 'Initialize Flask app with blueprints', 1, 2, 1, 'closed', 'high'),
        ('Write auth middleware', 'JWT-based authentication layer', 1, 3, 1, 'open', 'high'),
        ('API endpoint documentation', 'Document all REST endpoints in OpenAPI', 1, 2, 1, 'open', 'medium'),
        ('Design home screen mockups', 'Figma mockups for main navigation', 2, 4, 1, 'closed', 'medium'),
        ('Implement push notifications', 'Firebase Cloud Messaging integration', 2, 4, 1, 'open', 'high'),
        ('Create S3 bucket policies', 'Restrict access to analytics bucket', 3, 5, 2, 'open', 'high'),
        ('Write Spark jobs for ETL', 'PySpark transformation scripts', 3, 3, 2, 'open', 'medium'),
        ('Set up Airflow DAGs', 'Schedule pipeline runs with Airflow', 3, 5, 2, 'open', 'medium'),
        ('Login page design', 'OAuth2 login flow with Google SSO', 4, 4, 3, 'open', 'high'),
        ('Customer dashboard', 'Usage metrics and billing overview', 4, 4, 3, 'planning', 'medium'),
        ('Docker registry setup', 'Private registry with access controls', 5, 2, 1, 'closed', 'high'),
        ('GitHub Actions templates', 'Reusable workflow templates', 5, 5, 1, 'open', 'medium'),
    ]
    conn.executemany(
        'INSERT INTO tasks (title, description, project_id, assignee_id, creator_id, status, priority) VALUES (?, ?, ?, ?, ?, ?, ?)',
        tasks
    )

    # Seed task comments
    comments = [
        (1, 1, 'Finished. Used Blueprints pattern as discussed.'),
        (1, 2, 'Looks good, merged to main.'),
        (2, 3, 'Working on it, almost done with token refresh logic.'),
        (3, 2, 'Should we use Swagger UI or Redoc?'),
        (3, 1, 'Use Redoc, looks cleaner for external consumers.'),
        (6, 5, 'Need confirmation on which regions to lock down.'),
        (6, 2, 'US-east-1 and EU-west-1 only per compliance team.'),
        (11, 2, 'Registry is up at registry.internal.corp'),
        (12, 5, 'Template for Python microservices is ready to review.'),
    ]
    conn.executemany(
        'INSERT INTO task_comments (task_id, user_id, body) VALUES (?, ?, ?)',
        comments
    )

    # Seed notifications for users
    notifications = [
        (1, 'Project "Backend API Rewrite" was created successfully.', 1),
        (2, 'You were assigned to task "Set up Flask project structure".', 1),
        (2, 'Task "Set up Flask project structure" was closed.', 1),
        (3, 'You were assigned to task "Write auth middleware".', 0),
        (4, 'You were added to project "Mobile App v2".', 1),
        (5, 'You were added to project "Data Pipeline".', 0),
    ]
    conn.executemany(
        'INSERT INTO notifications (user_id, message, is_read) VALUES (?, ?, ?)',
        notifications
    )

    # Seed audit log
    audit_entries = [
        (1, 'project.create', 'Created project: Backend API Rewrite', '10.0.0.1'),
        (1, 'project.create', 'Created project: Mobile App v2', '10.0.0.1'),
        (2, 'task.create', 'Created task: Set up Flask project structure', '10.0.0.2'),
        (1, 'user.login', 'Login successful', '10.0.0.1'),
        (2, 'user.login', 'Login successful', '10.0.0.2'),
        (3, 'user.login', 'Login successful', '10.0.0.3'),
    ]
    conn.executemany(
        'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
        audit_entries
    )

    conn.commit()
    conn.close()
    logger.info("Seed data inserted successfully")