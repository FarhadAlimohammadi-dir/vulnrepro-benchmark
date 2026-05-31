import sqlite3
import os
import hashlib
import bcrypt

DB_PATH = os.path.join('data', 'taskflow.db')
os.makedirs('data', exist_ok=True)


def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def init_database():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    with open('models/schema.sql', 'r') as f:
        conn.executescript(f.read())

    users = [
        ('alice', 'alice@taskflow.io', hash_password('AlicePass123!'), 'admin', 'Alice Chen'),
        ('bob', 'bob@taskflow.io', hash_password('BobPass123!'), 'member', 'Bob Martinez'),
        ('charlie', 'charlie@taskflow.io', hash_password('CharliePass123!'), 'member', 'Charlie Kim'),
        ('diana', 'diana@taskflow.io', hash_password('Diana2024!'), 'member', 'Diana Okonkwo'),
        ('evan', 'evan@taskflow.io', hash_password('Evan2024!'), 'member', 'Evan Patel'),
    ]

    for u in users:
        try:
            conn.execute(
                'INSERT INTO users (username, email, password_hash, role, full_name) VALUES (?,?,?,?,?)',
                u
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()

    alice_id = conn.execute('SELECT id FROM users WHERE username=?', ('alice',)).fetchone()[0]
    bob_id = conn.execute('SELECT id FROM users WHERE username=?', ('bob',)).fetchone()[0]
    charlie_id = conn.execute('SELECT id FROM users WHERE username=?', ('charlie',)).fetchone()[0]

    projects = [
        ('TaskFlow Platform', 'Core platform development', alice_id, 'active', 'high'),
        ('Mobile App v2', 'iOS and Android redesign', bob_id, 'active', 'high'),
        ('API Gateway Migration', 'Move to new API gateway', alice_id, 'active', 'medium'),
        ('Data Analytics Dashboard', 'BI reporting suite', charlie_id, 'active', 'medium'),
        ('DevOps Infrastructure', 'K8s migration project', alice_id, 'completed', 'high'),
        ('Customer Portal', 'Self-service customer portal', bob_id, 'active', 'low'),
        ('Security Audit', 'Annual pen test remediation', alice_id, 'active', 'high'),
    ]

    for p in projects:
        try:
            conn.execute(
                'INSERT INTO projects (name, description, owner_id, status, priority) VALUES (?,?,?,?,?)',
                p
            )
        except Exception:
            pass

    conn.commit()

    proj1 = conn.execute('SELECT id FROM projects WHERE name=?', ('TaskFlow Platform',)).fetchone()[0]
    proj2 = conn.execute('SELECT id FROM projects WHERE name=?', ('Mobile App v2',)).fetchone()[0]

    tasks = [
        ('Implement OAuth2 provider', 'Add OAuth2 support for SSO', proj1, alice_id, 'in_progress', 'high', '2024-12-01'),
        ('Redesign login page', 'New branding for login flow', proj1, bob_id, 'todo', 'medium', '2024-11-15'),
        ('Fix pagination bug', 'Tasks list pagination off by one', proj1, charlie_id, 'done', 'low', '2024-10-30'),
        ('Add dark mode', 'User-requested dark theme', proj2, bob_id, 'in_progress', 'medium', '2024-12-15'),
        ('Push notifications', 'Firebase push notification setup', proj2, charlie_id, 'todo', 'high', '2024-12-01'),
        ('Performance profiling', 'Identify slow DB queries', proj1, alice_id, 'todo', 'high', '2024-11-20'),
        ('Write API docs', 'OpenAPI spec for v2 endpoints', proj1, bob_id, 'in_progress', 'medium', '2024-11-30'),
        ('User onboarding flow', 'First-time user walkthrough', proj2, alice_id, 'todo', 'high', '2024-12-10'),
        ('Fix memory leak', 'Node worker memory leak', proj1, charlie_id, 'done', 'high', '2024-10-15'),
        ('Add rate limiting', 'API rate limiting middleware', proj1, alice_id, 'in_progress', 'high', '2024-11-25'),
        ('Localization support', 'i18n for 5 languages', proj2, bob_id, 'todo', 'medium', '2025-01-15'),
        ('Accessibility audit', 'WCAG 2.1 compliance check', proj2, charlie_id, 'todo', 'medium', '2024-12-20'),
    ]

    for t in tasks:
        try:
            conn.execute(
                'INSERT INTO tasks (title, description, project_id, assignee_id, status, priority, due_date) VALUES (?,?,?,?,?,?,?)',
                t
            )
        except Exception:
            pass

    conn.commit()

    audit_entries = [
        (alice_id, 'user.login', 'user', alice_id, 'Successful login', '10.0.0.1'),
        (bob_id, 'user.login', 'user', bob_id, 'Successful login', '10.0.0.2'),
        (alice_id, 'project.create', 'project', 1, 'Created TaskFlow Platform', '10.0.0.1'),
        (alice_id, 'task.assign', 'task', 1, 'Assigned OAuth2 task to self', '10.0.0.1'),
        (charlie_id, 'task.complete', 'task', 3, 'Marked pagination bug as done', '10.0.0.3'),
    ]

    for entry in audit_entries:
        try:
            conn.execute(
                'INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?,?,?,?,?,?)',
                entry
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    print('Database initialized successfully')


if __name__ == '__main__':
    init_database()