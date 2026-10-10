from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Paper
from app.services import llm

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    n = 0
    try:
        n = Paper.query.count()
    except Exception:
        db.session.rollback()
    return jsonify(status="ok", papers=n)


@bp.get("/api/config")
def public_config():
    return jsonify(
        {
            "llm": llm.llm_status(),
            "search_modes": ["semantic", "keyword", "hybrid"],
            "discovery_sources": ["arxiv", "openalex", "semantic_scholar"],
        }
    )
