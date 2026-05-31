import logging
from models.database import get_db

logger = logging.getLogger(__name__)


def get_all_clusters():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, name, bootstrap_servers, description, status, created_at FROM clusters ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_cluster(cluster_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, bootstrap_servers, description, status, created_at FROM clusters WHERE id = ?",
            (cluster_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_cluster(name, bootstrap_servers, description=None):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO clusters (name, bootstrap_servers, description, status) VALUES (?, ?, ?, 'unknown')",
            (name, bootstrap_servers, description)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_cluster_metrics(cluster_id):
    conn = get_db()
    try:
        topic_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM topics WHERE cluster_id = ?", (cluster_id,)
        ).fetchone()['cnt']
        msg_count = conn.execute(
            """SELECT COUNT(*) as cnt FROM messages m
               JOIN topics t ON m.topic_id = t.id
               WHERE t.cluster_id = ?""",
            (cluster_id,)
        ).fetchone()['cnt']
        return {
            "cluster_id": cluster_id,
            "topic_count": topic_count,
            "message_count": msg_count,
            "broker_count": 3,
            "under_replicated_partitions": 0,
            "active_controller": 1,
        }
    finally:
        conn.close()


def get_topics_for_cluster(cluster_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, name, partitions, replication_factor, cleanup_policy, retention_bytes, created_at FROM topics WHERE cluster_id = ? ORDER BY name",
            (cluster_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_topic(cluster_id, name, partitions=1, cleanup_policy='delete', retention_bytes=-1):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM topics WHERE cluster_id = ? AND name = ?",
            (cluster_id, name)
        ).fetchone()
        if existing:
            return existing['id']
        cursor = conn.execute(
            "INSERT INTO topics (cluster_id, name, partitions, cleanup_policy, retention_bytes) VALUES (?, ?, ?, ?, ?)",
            (cluster_id, name, partitions, cleanup_policy, retention_bytes)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_topic(cluster_id, topic_name):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, partitions, replication_factor, cleanup_policy, retention_bytes, created_at FROM topics WHERE cluster_id = ? AND name = ?",
            (cluster_id, topic_name)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_messages_for_topic(topic_id, limit=100, offset=0):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, partition, offset_val, msg_key, msg_value, headers, timestamp FROM messages WHERE topic_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (topic_id, limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def post_message(topic_id, partition, msg_key, msg_value, headers=None):
    conn = get_db()
    try:
        max_offset = conn.execute(
            "SELECT COALESCE(MAX(offset_val), -1) as mo FROM messages WHERE topic_id = ? AND partition = ?",
            (topic_id, partition)
        ).fetchone()['mo']
        new_offset = max_offset + 1
        cursor = conn.execute(
            "INSERT INTO messages (topic_id, partition, offset_val, msg_key, msg_value, headers) VALUES (?, ?, ?, ?, ?, ?)",
            (topic_id, partition, new_offset, msg_key, msg_value, headers)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_cluster_config(cluster_id, configs):
    conn = get_db()
    try:
        for key, value in configs.items():
            conn.execute(
                """INSERT INTO cluster_configs (cluster_id, config_key, config_value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(cluster_id) DO UPDATE SET config_value=excluded.config_value, updated_at=CURRENT_TIMESTAMP""",
                (cluster_id, key, str(value))
            )
        conn.commit()
        return True
    finally:
        conn.close()


def get_audit_logs(limit=50):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, user_id, action, resource_type, resource_id, details, ip_address, created_at FROM audit_log ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def write_audit_log(user_id, action, resource_type, resource_id, details, ip_address):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, resource_type, str(resource_id), details, ip_address)
        )
        conn.commit()
    finally:
        conn.close()