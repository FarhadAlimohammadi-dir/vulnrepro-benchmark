import sqlite3
import os
import bcrypt
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/streamdash.db')


def get_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bootstrap_servers TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'unknown',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            partitions INTEGER DEFAULT 1,
            replication_factor INTEGER DEFAULT 1,
            cleanup_policy TEXT DEFAULT 'delete',
            retention_bytes INTEGER DEFAULT -1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cluster_id) REFERENCES clusters(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            partition INTEGER DEFAULT 0,
            offset_val INTEGER DEFAULT 0,
            msg_key TEXT,
            msg_value TEXT,
            headers TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS cluster_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER NOT NULL,
            config_key TEXT NOT NULL,
            config_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cluster_id) REFERENCES clusters(id)
        );
    """)

    # Seed users
    users = [
        ('alice', 'AlicePass123!', 'admin'),
        ('bob', 'BobPass123!', 'viewer'),
        ('charlie', 'CharliePass123!', 'operator'),
    ]
    for username, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, pw_hash, role)
        )

    # Seed clusters
    cursor.executemany(
        "INSERT OR IGNORE INTO clusters (id, name, bootstrap_servers, description, status) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 'production', 'kafka-prod-1:9092,kafka-prod-2:9092', 'Main production cluster', 'healthy'),
            (2, 'staging', 'kafka-staging-1:9092', 'Staging environment', 'healthy'),
            (3, 'analytics', 'kafka-analytics-1:9092', 'Analytics pipeline cluster', 'degraded'),
        ]
    )

    # Seed topics
    cursor.executemany(
        "INSERT OR IGNORE INTO topics (id, cluster_id, name, partitions, cleanup_policy) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, 'user-events', 12, 'delete'),
            (2, 1, 'order-processing', 8, 'delete'),
            (3, 1, 'payment-notifications', 4, 'compact'),
            (4, 2, 'test-events', 2, 'delete'),
            (5, 3, 'clickstream', 16, 'delete'),
            (6, 3, 'page-views', 8, 'delete'),
        ]
    )

    # Seed messages
    seed_messages = [
        (1, 1, 0, 0, 'user-123', '{"event":"login","userId":"user-123","ts":1700000001}', None),
        (2, 1, 0, 1, 'user-456', '{"event":"logout","userId":"user-456","ts":1700000002}', None),
        (3, 1, 0, 2, 'user-789', '{"event":"purchase","userId":"user-789","amount":59.99}', None),
        (4, 2, 0, 0, 'order-001', '{"orderId":"order-001","status":"created","total":120.00}', None),
        (5, 2, 0, 1, 'order-002', '{"orderId":"order-002","status":"shipped","carrier":"UPS"}', None),
        (6, 2, 1, 0, 'order-003', '{"orderId":"order-003","status":"delivered","rating":5}', None),
        (7, 3, 0, 0, 'pay-001', '{"paymentId":"pay-001","status":"success","method":"card"}', None),
        (8, 4, 0, 0, 'test-key-1', '{"test":true,"data":"hello world"}', None),
        (9, 5, 0, 0, 'click-001', '{"sessionId":"abc","page":"/home","duration":3200}', None),
        (10, 5, 0, 1, 'click-002', '{"sessionId":"def","page":"/products","duration":8100}', None),
    ]
    for row in seed_messages:
        cursor.execute(
            "INSERT OR IGNORE INTO messages (id, topic_id, partition, offset_val, msg_key, msg_value, headers) VALUES (?, ?, ?, ?, ?, ?, ?)",
            row
        )

    # Seed cluster configs
    cursor.executemany(
        "INSERT OR IGNORE INTO cluster_configs (cluster_id, config_key, config_value) VALUES (?, ?, ?)",
        [
            (1, 'auto.offset.reset', 'earliest'),
            (1, 'max.poll.records', '500'),
            (2, 'auto.offset.reset', 'latest'),
            (3, 'compression.type', 'snappy'),
        ]
    )

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")