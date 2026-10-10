from flask import Blueprint, current_app, jsonify, request

from app.models import Keyword, Paper, Section
from app.services.arxiv_client import search_arxiv
from app.services.ingest import (
    create_paper_record,
    delete_paper,
    import_from_arxiv,
    save_upload,
    schedule_ingest,
    sha256_file,
    validate_upload,
)
from app.services.bulk_import import queue_bulk_import
from app.services.discovery import discover
from app.services.search_engine import similar_papers

bp = Blueprint("papers", __name__)


@bp.get("")
def list_papers():
    status = request.args.get("status")
    q = Paper.query.order_by(Paper.created_at.desc())
    if status:
        q = q.filter_by(status=status)
    papers = q.all()
    return jsonify({"papers": [p.to_dict() for p in papers], "total": len(papers)})


@bp.post("/discover")
def discover_papers():
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or request.args.get("q") or "").strip()
    if not query:
        return jsonify(error="bad_request", message="query is required"), 400
    sources = body.get("sources") or ["arxiv", "openalex", "semantic_scholar"]
    max_per = int(body.get("max_per_source") or 15)
    return jsonify(discover(query, sources=sources, max_per_source=max_per))


@bp.post("/import-bulk")
def import_bulk():
    body = request.get_json(silent=True) or {}
    items = body.get("items") or []
    if not items:
        return jsonify(error="bad_request", message="items array required"), 400
    if len(items) > 200:
        return jsonify(error="bad_request", message="Max 200 items per request"), 400
    delay = float(body.get("delay_sec") or 1.5)
    n = queue_bulk_import(items, delay_sec=delay)
    return jsonify({"queued": n, "message": "Imports running in background; poll /status per paper"}), 202


@bp.get("/<int:paper_id>")
def get_paper(paper_id: int):
    paper = Paper.query.get_or_404(paper_id)
    keywords = [k.to_dict() for k in paper.keywords.order_by(Keyword.score.desc()).all()]
    sections = [s.to_dict() for s in paper.sections.order_by(Section.order).all()]
    data = paper.to_dict(include_summary=True)
    data["keywords"] = keywords
    data["sections"] = sections
    return jsonify(data)


@bp.get("/<int:paper_id>/status")
def paper_status(paper_id: int):
    paper = Paper.query.get_or_404(paper_id)
    return jsonify(
        {
            "id": paper.id,
            "status": paper.status,
            "progress": paper.progress,
            "status_message": paper.status_message,
        }
    )


@bp.delete("/<int:paper_id>")
def remove_paper(paper_id: int):
    if not delete_paper(paper_id):
        return jsonify(error="not_found", message="Paper not found"), 404
    return jsonify({"ok": True, "deleted": paper_id})


@bp.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify(error="bad_request", message="Missing file field"), 400
    fs = request.files["file"]
    try:
        validate_upload(fs, int(current_app.config.get("MAX_UPLOAD_MB", 25)))
    except ValueError as exc:
        return jsonify(error="bad_request", message=str(exc)), 400

    dest = current_app.config["DATA_DIR"] / "uploads"
    path = save_upload(fs, dest)
    file_hash = sha256_file(path)
    existing = Paper.query.filter_by(file_hash=file_hash).first()
    if existing:
        try:
            path.unlink()
        except OSError:
            pass
        return jsonify({"paper": existing.to_dict(), "deduplicated": True}), 200

    paper = create_paper_record(
        title=request.form.get("title") or path.stem,
        authors=request.form.get("authors") or "",
        source="upload",
        file_hash=file_hash,
        file_path=str(path),
        status="queued",
        status_message="Queued",
        progress=0,
    )
    schedule_ingest(current_app._get_current_object(), paper.id)
    return jsonify({"paper": paper.to_dict(), "deduplicated": False}), 202


@bp.get("/arxiv/search")
def arxiv_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify(error="bad_request", message="Query required"), 400
    try:
        results = search_arxiv(q, max_results=10)
    except Exception as exc:  # noqa: BLE001
        return jsonify(error="upstream", message=str(exc)), 502
    return jsonify({"results": results})


@bp.post("/import-arxiv")
def import_arxiv():
    body = request.get_json(silent=True) or {}
    arxiv_id = (body.get("arxiv_id") or request.args.get("arxiv_id") or "").strip()
    query = (body.get("query") or "").strip()
    if not arxiv_id and query:
        results = search_arxiv(query, max_results=10)
        return jsonify({"results": results, "pick": True})
    if not arxiv_id:
        return jsonify(error="bad_request", message="arxiv_id or query required"), 400
    existing = Paper.query.filter_by(arxiv_id=arxiv_id.replace("arxiv:", "")).first()
    if existing:
        return jsonify({"paper": existing.to_dict(), "deduplicated": True}), 200
    try:
        paper = import_from_arxiv(arxiv_id)
    except ValueError as exc:
        return jsonify(error="not_found", message=str(exc)), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify(error="upstream", message=str(exc)), 502
    return jsonify({"paper": paper.to_dict(), "deduplicated": False}), 202


@bp.get("/<int:paper_id>/similar")
def similar(paper_id: int):
    Paper.query.get_or_404(paper_id)
    return jsonify({"similar": similar_papers(paper_id, k=5)})
