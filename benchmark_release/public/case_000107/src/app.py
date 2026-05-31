import os
import sqlite3
import hashlib
import logging
from flask import Flask, g
from flask_login import LoginManager

from routes.auth import auth_bp
from routes.notes import notes_bp
from routes.admin import admin_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-prod-abc123xyz")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login_page"

DATABASE = "notes.db"


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                is_public INTEGER DEFAULT 0,
                share_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                target_id INTEGER,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (note_id) REFERENCES notes(id)
            )
        """)

        def hash_pw(pw):
            return hashlib.sha256(pw.encode()).hexdigest()

        # Seed users
        users = [
            ("alice", hash_pw("AlicePass123!"), "user"),
            ("bob", hash_pw("BobPass123!"), "user"),
            ("charlie", hash_pw("CharliePass123!"), "user"),
            ("admin", hash_pw("Adm1nS3cur3!"), "admin"),
        ]
        for username, pw_hash, role in users:
            cursor.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, pw_hash, role)
            )

        # Seed notes with realistic content
        sample_notes = [
            (1, "Q3 Planning Notes", "<h2>Q3 Goals</h2><p>Increase user retention by 15%.</p><ul><li>Launch referral program</li><li>Improve onboarding flow</li></ul>", 1),
            (1, "Meeting Minutes - 2024-01-15", "<p>Attendees: Alice, Bob, Charlie</p><p>Discussion: Product roadmap for H1.</p>", 0),
            (2, "Recipe Collection", "<h3>Pasta Carbonara</h3><p>Ingredients: eggs, pecorino, guanciale, pepper.</p>", 1),
            (2, "Books to Read", "<ul><li>The Pragmatic Programmer</li><li>Clean Code</li><li>Designing Data-Intensive Applications</li></ul>", 0),
            (3, "Travel Itinerary", "<h2>Japan Trip</h2><p>Day 1: Tokyo arrival. Day 2: Shibuya, Harajuku.</p>", 1),
            (3, "Study Notes - Algorithms", "<p>Binary search: O(log n). Merge sort: O(n log n).</p>", 0),
            (1, "Project Kickoff", "<p>New client onboarded. Initial scope defined.</p>", 0),
            (2, "Workout Log", "<table><tr><th>Day</th><th>Exercise</th></tr><tr><td>Mon</td><td>Squats 3x10</td></tr></table>", 0),
            (3, "Conference Talk Outline", "<h1>Talk: Modern Distributed Systems</h1><ol><li>Intro</li><li>CAP Theorem</li><li>Demo</li></ol>", 1),
            (1, "Bug Reports Summary", "<p>Open issues: 12. Critical: 1. Major: 4.</p>", 0),
        ]
        for user_id, title, content, is_public in sample_notes:
            cursor.execute(
                "INSERT OR IGNORE INTO notes (user_id, title, content, is_public) VALUES (?, ?, ?, ?)",
                (user_id, title, content, is_public)
            )

        # Seed audit log
        cursor.execute("INSERT OR IGNORE INTO audit_log (user_id, action, target_id, ip_address) VALUES (1, 'login', NULL, '127.0.0.1')")
        cursor.execute("INSERT OR IGNORE INTO audit_log (user_id, action, target_id, ip_address) VALUES (2, 'login', NULL, '10.0.0.1')")
        cursor.execute("INSERT OR IGNORE INTO audit_log (user_id, action, target_id, ip_address) VALUES (1, 'create_note', 1, '127.0.0.1')")

        db.commit()
        db.close()
        logger.info("Database initialized with seed data")


app.get_db = get_db
app.register_blueprint(auth_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(admin_bp)


from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role


@login_manager.user_loader
def load_user(user_id):
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    if row:
        return User(row["id"], row["username"], row["role"])
    return None


if __name__ == "__main__":
    init_db()
    logger.info("Starting Notes application on port 9000")
    app.run(host="0.0.0.0", port=9000, debug=False)