import os
import logging
from flask import Flask, render_template, redirect, url_for

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['JSON_SORT_KEYS'] = False

    # Register API blueprint
    from routes.api import api_bp
    app.register_blueprint(api_bp)

    @app.route('/')
    def index():
        from services.cluster_service import get_all_clusters
        clusters = get_all_clusters()
        return render_template('index.html', clusters=clusters)

    @app.route('/clusters/<int:cluster_id>')
    def cluster_detail(cluster_id):
        from services.cluster_service import get_cluster, get_topics_for_cluster, get_cluster_metrics
        cluster = get_cluster(cluster_id)
        if not cluster:
            return "Cluster not found", 404
        topics = get_topics_for_cluster(cluster_id)
        metrics = get_cluster_metrics(cluster_id)
        return render_template('cluster.html', cluster=cluster, topics=topics, metrics=metrics)

    @app.route('/clusters/<int:cluster_id>/topics/<topic_name>')
    def topic_detail(cluster_id, topic_name):
        from services.cluster_service import get_cluster, get_topic, get_messages_for_topic
        cluster = get_cluster(cluster_id)
        topic = get_topic(cluster_id, topic_name)
        if not topic:
            return "Topic not found", 404
        messages = get_messages_for_topic(topic['id'], limit=50)
        return render_template('topic.html', cluster=cluster, topic=topic, messages=messages)

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error("Server error: %s", e)
        return {'error': 'Internal server error'}, 500

    return app


if __name__ == '__main__':
    from models.database import init_db
    init_db()
    app = create_app()
    app.run(host='0.0.0.0', port=9000, debug=False)