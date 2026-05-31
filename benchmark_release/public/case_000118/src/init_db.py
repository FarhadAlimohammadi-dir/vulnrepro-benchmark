import sqlite3
import os
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'meridian.db')


def hash_password(password):
    salt = 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7b8c9d0e1f2a3b4c5d6a7b8c9d0e1f2'
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return salt + hashed


def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'employee',
            department TEXT DEFAULT 'General',
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            position TEXT,
            department_id INTEGER,
            hire_date TEXT,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        );

        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            author TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    departments = [
        'Engineering', 'Human Resources', 'Finance', 'Marketing',
        'Operations', 'Legal', 'Sales', 'IT Support'
    ]
    for dept in departments:
        cur.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)", (dept,))

    users = [
        ('alice', 'alice@meridian.internal', hash_password('AlicePass123!'), 'admin', 'Human Resources'),
        ('bob', 'bob@meridian.internal', hash_password('BobPass123!'), 'employee', 'Engineering'),
        ('charlie', 'charlie@meridian.internal', hash_password('CharliePass123!'), 'employee', 'Finance'),
        ('diana.h', 'diana.h@meridian.internal', hash_password('Diana#2024'), 'manager', 'Marketing'),
        ('erwin.t', 'erwin.t@meridian.internal', hash_password('Erwin$pass9'), 'employee', 'Operations'),
        ('fiona.m', 'fiona.m@meridian.internal', hash_password('FionaM!009'), 'employee', 'Legal'),
        ('george.p', 'george.p@meridian.internal', hash_password('GeoPass#77'), 'employee', 'Sales'),
        ('hr.admin', 'hradmin@meridian.internal', hash_password('HRadm1n!22'), 'admin', 'Human Resources'),
    ]
    for uname, email, pw_hash, role, dept in users:
        cur.execute("""
            INSERT OR IGNORE INTO users (username, email, password_hash, role, department)
            VALUES (?, ?, ?, ?, ?)
        """, (uname, email, pw_hash, role, dept))

    emp_data = [
        ('Alice', 'Morgan', 'alice@meridian.internal', 'HR Director', 2),
        ('Bob', 'Chen', 'bob@meridian.internal', 'Senior Engineer', 1),
        ('Charlie', 'Davis', 'charlie@meridian.internal', 'Financial Analyst', 3),
        ('Diana', 'Hunt', 'diana.h@meridian.internal', 'Marketing Manager', 4),
        ('Erwin', 'Torres', 'erwin.t@meridian.internal', 'Operations Lead', 5),
        ('Fiona', 'Mitchell', 'fiona.m@meridian.internal', 'Legal Counsel', 6),
        ('George', 'Patel', 'george.p@meridian.internal', 'Account Executive', 7),
        ('Hannah', 'Reeves', 'h.reeves@meridian.internal', 'Software Engineer', 1),
        ('Ivan', 'Kozlov', 'i.kozlov@meridian.internal', 'DevOps Engineer', 1),
        ('Julia', 'Santos', 'j.santos@meridian.internal', 'Recruiter', 2),
        ('Kevin', 'Walsh', 'k.walsh@meridian.internal', 'Financial Controller', 3),
        ('Laura', 'Kim', 'l.kim@meridian.internal', 'Brand Strategist', 4),
        ('Marcus', 'Obi', 'm.obi@meridian.internal', 'IT Support Specialist', 8),
        ('Nina', 'Frost', 'n.frost@meridian.internal', 'Sales Representative', 7),
        ('Oscar', 'Lange', 'o.lange@meridian.internal', 'Legal Assistant', 6),
    ]
    for fn, ln, em, pos, dept_id in emp_data:
        cur.execute("""
            INSERT OR IGNORE INTO employees (first_name, last_name, email, position, department_id, hire_date)
            VALUES (?, ?, ?, ?, ?, date('now', '-' || (abs(random()) % 1000) || ' days'))
        """, (fn, ln, em, pos, dept_id))

    announcements = [
        ('Q3 Performance Reviews', 'Performance review season begins next Monday. All managers should schedule 1:1s with direct reports before end of month.', 'HR Team'),
        ('New Remote Work Policy', 'Effective September 1st, employees may work remotely up to 3 days per week. Please review the updated policy document in the intranet.', 'Operations'),
        ('Office Closure – Public Holiday', 'The Meridian offices will be closed on the upcoming public holiday. Emergency contacts are listed in the intranet portal.', 'Facilities'),
        ('Updated Leave Request Process', 'All leave requests must now be submitted at least 5 business days in advance via this portal. See HR for exceptions.', 'HR Team'),
        ('IT Security Reminder', 'Please ensure your workstation is locked when stepping away from your desk. Report any suspicious activity to IT immediately.', 'IT Support'),
    ]
    for title, body, author in announcements:
        cur.execute("""
            INSERT OR IGNORE INTO announcements (title, body, author) VALUES (?, ?, ?)
        """, (title, body, author))

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


if __name__ == '__main__':
    init()