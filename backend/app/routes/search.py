from flask import Blueprint, jsonify, request

from app.services.search_engine import search

bp = Blueprint("search", __name__)


@bp.get("/search")
def search_route():
    q = request.args.get("q") or request.args.get("query") or ""
    mode = (request.args.get("mode") or "hybrid").lower()
    if mode not in {"semantic", "keyword", "hybrid"}:
        return jsonify(error="bad_request", message="mode must be semantic, keyword, or hybrid"), 400
    try:
        k = int(request.args.get("k") or 10)
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("page_size") or k)
        year_from = request.args.get("year_from") or request.args.get("year")
        year_to = request.args.get("year_to")
        year_from_i = int(year_from) if year_from else None
        year_to_i = int(year_to) if year_to else None
        if year_from and not year_to and "year" in request.args:
            year_to_i = year_from_i
    except ValueError:
        return jsonify(error="bad_request", message="Invalid numeric parameter"), 400

    result = search(
        query=q,
        k=k,
        mode=mode,
        section=request.args.get("section") or None,
        year_from=year_from_i,
        year_to=year_to_i,
        author=request.args.get("author") or None,
        page=page,
        page_size=page_size,
    )
    return jsonify(result)
