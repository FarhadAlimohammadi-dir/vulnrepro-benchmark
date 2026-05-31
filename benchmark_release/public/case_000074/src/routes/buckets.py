import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.bucket_service import (
    create_bucket, list_buckets, get_bucket_objects,
    get_object_content, delete_bucket
)

logger = logging.getLogger("functionforge.buckets_route")
buckets_bp = Blueprint("buckets", __name__)


@buckets_bp.route("/", methods=["POST"])
@login_required
def api_create_bucket():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    result = create_bucket(name, current_user.id)
    if result is None:
        return jsonify({"error": "bucket name already taken"}), 409
    return jsonify(result), 201


@buckets_bp.route("/", methods=["GET"])
@login_required
def api_list_buckets():
    buckets = list_buckets(current_user.id)
    return jsonify(buckets), 200


@buckets_bp.route("/<bucket_name>/objects", methods=["GET"])
@login_required
def api_list_objects(bucket_name):
    objects = get_bucket_objects(bucket_name, current_user.id)
    if objects is None:
        return jsonify({"error": "bucket not found"}), 404
    return jsonify(objects), 200


@buckets_bp.route("/<bucket_name>/objects/<path:object_key>", methods=["GET"])
@login_required
def api_get_object(bucket_name, object_key):
    content = get_object_content(bucket_name, object_key, current_user.id)
    if content is None:
        return jsonify({"error": "object not found"}), 404
    return jsonify({"content": content}), 200


@buckets_bp.route("/<bucket_name>", methods=["DELETE"])
@login_required
def api_delete_bucket(bucket_name):
    ok = delete_bucket(bucket_name, current_user.id)
    if not ok:
        return jsonify({"error": "bucket not found"}), 404
    return jsonify({"status": "deleted"}), 200