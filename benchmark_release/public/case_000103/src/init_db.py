"""
Database initialisation and seeding script.
Run once at container startup via Dockerfile.
"""
import hashlib
import os
import sqlite3

from app.database import init_db, get_db
from app.sanitizer import sanitize_post_content, slugify


def hash_pw(password: str) -> str:
    import os as _os
    salt = "staticseesalt01"  # deterministic for seed data
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
    return f"{digest.hex()}:{salt}"


USERS = [
    ("alice",   "alice@contenthub.io",   "AlicePass123!", "editor"),
    ("bob",     "bob@contenthub.io",     "BobPass123!",   "author"),
    ("charlie", "charlie@contenthub.io", "CharliePass123!", "author"),
    ("diana",   "diana@contenthub.io",   "DianaPass456!",  "author"),
    ("erin",    "erin@contenthub.io",    "ErinPass789!",   "author"),
]

POSTS = [
    ("alice", "Getting Started with Flask", "tech",
     "<p>Flask is a lightweight WSGI web application framework. It's easy to get started with and scales well.</p><p>Install with <code>pip install flask</code> and you're ready to go.</p>"),
    ("bob", "Understanding Python Decorators", "tech",
     "<p>Decorators are a powerful feature of Python that allow you to modify functions at definition time.</p>"),
    ("charlie", "The Philosophy of Open Source", "opinion",
     "<p>Open source software has transformed the technology landscape over the past three decades.</p>"),
    ("alice", "Ten Tips for Better Code Reviews", "tutorial",
     "<p>Code reviews are one of the most effective tools we have for maintaining code quality.</p><ul><li>Be respectful</li><li>Focus on the code, not the person</li><li>Ask questions rather than making demands</li></ul>"),
    ("bob", "A Brief History of the Internet", "science",
     "<p>The internet grew from ARPANET, a US Defense Department project in the late 1960s.</p>"),
    ("diana", "Why Functional Programming Matters", "tech",
     "<p>Functional programming offers a different paradigm from imperative programming.</p>"),
    ("erin", "Book Review: The Pragmatic Programmer", "culture",
     "<p>This classic book by Hunt and Thomas remains as relevant today as when it was first published.</p>"),
    ("charlie", "Cloud Cost Optimisation Strategies", "tutorial",
     "<p>Cloud bills can spiral out of control quickly. Here are strategies to keep costs in check.</p>"),
    ("alice", "Introduction to SQL Indexing", "tutorial",
     "<p>Indexes are one of the most important tools for database performance.</p>"),
    ("bob", "Remote Work Productivity Guide", "culture",
     "<p>Working remotely requires discipline and the right environment.</p>"),
    ("diana", "Containerisation with Docker", "tech",
     "<p>Docker has revolutionised how we build and deploy applications.</p>"),
    ("erin", "The Future of AI in Software Development", "opinion",
     "<p>AI-assisted development tools are changing how engineers write code.</p>"),
]

COMMENTS = [
    (1, "bob", "Great introduction! Really helped me get started."),
    (1, "charlie", "Flask is my go-to framework for small projects."),
    (2, "alice", "Excellent explanation of decorators. Bookmarked."),
    (3, "diana", "Thought-provoking read. I agree with most of your points."),
    (4, "erin", "These code review tips should be mandatory reading for every dev team."),
    (5, "charlie", "I didn't realise ARPANET had such a long history before the web."),
    (6, "bob", "Functional programming changed how I think about problems."),
    (7, "alice", "I re-read The Pragmatic Programmer every few years."),
    (8, "diana", "Reserved instances saved us about 40% on our monthly bill."),
    (9, "erin", "Composite indexes are underused. Good point there."),
    (10, "charlie", "The async-friendly workspace tip is gold."),
]


def main():
    init_db()
    db = get_db()

    # Check if already seeded
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        db.close()
        return

    user_ids = {}
    for username, email, password, role in USERS:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, hash_pw(password), role)
        )
        user_ids[username] = cur.lastrowid

    post_ids = []
    for author, title, category, content in POSTS:
        rendered = sanitize_post_content(content)
        slug = slugify(title)
        cur = db.execute(
            """INSERT INTO posts (author_id, title, slug, content, rendered_content, status, category)
               VALUES (?, ?, ?, ?, ?, 'published', ?)""",
            (user_ids[author], title, slug, content, rendered, category)
        )
        post_ids.append(cur.lastrowid)

    for idx, commenter, body in COMMENTS:
        if idx - 1 < len(post_ids):
            db.execute(
                "INSERT INTO comments (post_id, author_id, body) VALUES (?, ?, ?)",
                (post_ids[idx - 1], user_ids[commenter], body)
            )

    db.commit()
    db.close()
    print("Database seeded successfully.")


if __name__ == "__main__":
    main()