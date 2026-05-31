import json
import logging
from flask import Blueprint, request, jsonify
from services import cluster_service
from services.message_filter import apply_filter

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ---- Cluster endpoints ----

@api_bp.route('/clusters', methods=['GET'])
def list_clusters():
    clusters = cluster_service.get_all_clusters()
    return jsonify(clusters)


@api_bp.route('/clusters', methods=['POST'])
def create_cluster():
    data = request.get_json(force=True)
    if not data or not data.get('name') or not data.get('bootstrapServers'):
        return jsonify({"error": "name and bootstrapServers are required"}), 400
    cluster_id = cluster_service.create_cluster(
        name=data['name'],
        bootstrap_servers=data['bootstrapServers'],
        description=data.get('description', '')
    )
    cluster_service.write_audit_log(
        None, 'CREATE', 'cluster', cluster_id, f"Created cluster {data['name']}", request.remote_addr
    )
    return jsonify({"id": cluster_id, "name": data['name']}), 201


@api_bp.route('/clusters/<int:cluster_id>', methods=['GET'])
def get_cluster(cluster_id):
    cluster = cluster_service.get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    return jsonify(cluster)


@api_bp.route('/clusters/<int:cluster_id>/metrics', methods=['GET'])
def cluster_metrics(cluster_id):
    cluster = cluster_service.get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    metrics = cluster_service.get_cluster_metrics(cluster_id)
    return jsonify(metrics)


@api_bp.route('/clusters/<int:cluster_id>/config', methods=['POST'])
def update_cluster_config(cluster_id):
    cluster = cluster_service.get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    data = request.get_json(force=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Config must be a JSON object"}), 400
    # SRE-2031: batches up to 50 items
    if len(data) > 50:
        return jsonify({"error": "Too many config keys"}), 400
    allowed_keys = {
        'auto.offset.reset', 'max.poll.records', 'compression.type',
        'retention.ms', 'retention.bytes', 'segment.bytes', 'cleanup.policy',
        'min.insync.replicas', 'replication.factor'
    }
    filtered = {k: v for k, v in data.items() if k in allowed_keys}
    cluster_service.update_cluster_config(cluster_id, filtered)
    cluster_service.write_audit_log(
        None, 'UPDATE_CONFIG', 'cluster', cluster_id,
        f"Updated {len(filtered)} config keys", request.remote_addr
    )
    return jsonify({"updated": len(filtered)})


# ---- Topic endpoints ----

@api_bp.route('/clusters/<int:cluster_id>/topics', methods=['GET'])
def list_topics(cluster_id):
    cluster = cluster_service.get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    topics = cluster_service.get_topics_for_cluster(cluster_id)
    return jsonify(topics)


@api_bp.route('/clusters/<int:cluster_id>/topics', methods=['POST'])
def create_topic(cluster_id):
    cluster = cluster_service.get_cluster(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    data = request.get_json(force=True)
    if not data or not data.get('name'):
        return jsonify({"error": "Topic name is required"}), 400
    configs = data.get('configs', {})
    topic_id = cluster_service.create_topic(
        cluster_id=cluster_id,
        name=data['name'],
        partitions=int(data.get('partitions', 1)),
        cleanup_policy=configs.get('cleanup.policy', 'delete'),
        retention_bytes=int(configs.get('retention.bytes', -1))
    )
    cluster_service.write_audit_log(
        None, 'CREATE', 'topic', topic_id, f"Created topic {data['name']} in cluster {cluster_id}",
        request.remote_addr
    )
    return jsonify({"id": topic_id, "name": data['name']}), 201


@api_bp.route('/clusters/<int:cluster_id>/topics/<topic_name>', methods=['GET'])
def get_topic(cluster_id, topic_name):
    topic = cluster_service.get_topic(cluster_id, topic_name)
    if not topic:
        return jsonify({"error": "Topic not found"}), 404
    return jsonify(topic)


# ---- Message endpoints ----

@api_bp.route('/clusters/<int:cluster_id>/topics/<topic_name>/messages', methods=['GET'])
def get_messages(cluster_id, topic_name):
    """
    Retrieve messages for a topic, with optional server-side filtering.
    Query params:
      - q: filter query string
      - filterType: STRING_CONTAINS | REGEX | KEY_EQUALS | PYTHON_EXPR
      - limit: max messages to return (default 100)
      - offset: pagination offset (default 0)
    """
    topic = cluster_service.get_topic(cluster_id, topic_name)
    if not topic:
        return jsonify({"error": "Topic not found"}), 404

    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    query = request.args.get('q', '')
    filter_type = request.args.get('filterType', 'STRING_CONTAINS')

    messages = cluster_service.get_messages_for_topic(topic['id'], limit=limit, offset=offset)

    if query:
        try:
            messages = apply_filter(messages, query, filter_type)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error("Filter error: %s", e)
            return jsonify({"error": "Filter execution error", "detail": str(e)}), 500

    cluster_service.write_audit_log(
        None, 'READ', 'messages', topic['id'],
        f"Queried topic {topic_name} with filter={filter_type} q={query[:80] if query else ''}",
        request.remote_addr
    )

    return jsonify({
        "topic": topic_name,
        "cluster_id": cluster_id,
        "count": len(messages),
        "messages": messages
    })


@api_bp.route('/clusters/<int:cluster_id>/topics/<topic_name>/messages', methods=['POST'])
def post_message(cluster_id, topic_name):
    topic = cluster_service.get_topic(cluster_id, topic_name)
    if not topic:
        return jsonify({"error": "Topic not found"}), 404
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    partition = int(data.get('partition', 0))
    msg_key = data.get('key', '')
    msg_value = data.get('content', data.get('value', ''))
    headers = json.dumps(data.get('headers', {})) if data.get('headers') else None

    msg_id = cluster_service.post_message(topic['id'], partition, msg_key, msg_value, headers)
    cluster_service.write_audit_log(
        None, 'PRODUCE', 'message', msg_id,
        f"Produced message to {topic_name} partition {partition}",
        request.remote_addr
    )
    return jsonify({"id": msg_id, "partition": partition}), 201


# ---- Audit log endpoint ----

@api_bp.route('/audit', methods=['GET'])
def audit_log():
    limit = min(int(request.args.get('limit', 50)), 200)
    logs = cluster_service.get_audit_logs(limit)
    return jsonify(logs)


# ---- Search endpoint (safe) ----

@api_bp.route('/search', methods=['GET'])
def search():
    """Global search across topics and cluster names."""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400
    if len(q) > 200:
        return jsonify({"error": "Query too long"}), 400

    from models.database import get_db
    conn = get_db()
    try:
        # Parameterized search - safe
        like_q = f"%{q}%"
        clusters = conn.execute(
            "SELECT id, name, 'cluster' as type FROM clusters WHERE name LIKE ? OR description LIKE ?",
            (like_q, like_q)
        ).fetchall()
        topics = conn.execute(
            "SELECT t.id, t.name, 'topic' as type FROM topics t WHERE t.name LIKE ?",
            (like_q,)
        ).fetchall()
        results = [dict(r) for r in clusters] + [dict(r) for r in topics]
        return jsonify({"results": results, "total": len(results)})
    finally:
        conn.close()