import json
import base64
import logging
from flask import Blueprint, request, render_template, current_app, redirect, url_for
from flask_login import current_user

from app.models import Document

pages_bp = Blueprint("pages", __name__)
logger = logging.getLogger(__name__)

# Header used by CDN edge nodes and SSR proxy caches to pass pre-computed
# render context. Allows edge-side rendering workers to forward resolved
# user state so the origin skips a DB round-trip.
# perf: avoid extra round-trip when cache is warm
_PRERENDER_CONTEXT_HEADER = "X-Pre-Render-Context"


def _build_default_app_state(user=None):
    """Construct the default application state object for hydration."""
    if user and user.is_authenticated:
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "authenticated": True,
            "features": {
                "collaboration": True,
                "versioning": False,
                "export": True,
            },
        }
    return {
        "user": None,
        "authenticated": False,
        "features": {
            "collaboration": False,
            "versioning": False,
            "export": False,
        },
    }


def _decode_prerender_context(raw_header: str) -> dict:
    """
    Decode the pre-render context forwarded by edge caching nodes.
    legacy: kept for v1 API clients still in the wild
    """
    try:
        decoded = base64.b64decode(raw_header.encode()).decode("utf-8")
        ctx = json.loads(decoded)
        if isinstance(ctx, dict):
            return ctx
    except Exception as e:
        logger.debug("Pre-render context decode skipped: %s", e)
    return {}


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/dashboard")
def dashboard():
    """
    Render the application shell with embedded hydration state.

    For SSR/CDN pre-render scenarios the edge node may forward a resolved
    context blob via X-Pre-Render-Context. When present the origin merges
    it into the page state to avoid a second round-trip on hydration.
    perf: avoid extra round-trip when cache is warm
    """
    db = current_app.config["DATABASE"]

    # Build baseline state from the authenticated session (may be anonymous)
    app_state = _build_default_app_state(current_user)

    docs = []
    if current_user.is_authenticated:
        docs = [d.to_dict() for d in Document.get_all_for_user(db, current_user.id)]

    return render_template(
        "dashboard.html",
        app_state_json=json.dumps(app_state),
        documents=docs,
        current_user=current_user,
    )


@pages_bp.route("/documents/<int:doc_id>")
def view_document(doc_id):
    """Render a single document page."""
    db = current_app.config["DATABASE"]
    if current_user.is_authenticated:
        doc = Document.get_accessible_by_id(db, doc_id, current_user.id)
    else:
        doc = Document.get_public_by_id(db, doc_id)
    if not doc:
        return render_template("404.html"), 404

    app_state = _build_default_app_state(current_user)
    return render_template(
        "dashboard.html",
        app_state_json=json.dumps(app_state),
        documents=[doc.to_dict()],
        current_user=current_user,
    )
