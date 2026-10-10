import json

from flask import Blueprint, jsonify, request

from app.extensions import db, limiter
from app.models import Keyword, Paper
from app.services import llm
from app.services.keywords import library_topics
from app.services.summarizer import summarize_paper
from app.utils.json_util import parse_json_loose

bp = Blueprint("analyze", __name__)


@bp.post("/papers/<int:paper_id>/summarize")
@limiter.limit("10/minute")
def summarize(paper_id: int):
    paper = Paper.query.get_or_404(paper_id)
    if paper.status != "ready":
        return jsonify(error="conflict", message="Paper is not ready yet"), 409
    regenerate = str(request.args.get("regenerate") or "").lower() in {"1", "true", "yes"}
    summary, mode = summarize_paper(paper, regenerate=regenerate)
    db.session.commit()
    return jsonify(
        {
            "summary": summary,
            "mode": mode,
            "llm_configured": llm.llm_configured(),
            "notice": None
            if mode == "llm"
            else "Extractive/cached summary (LLM not used or not configured).",
        }
    )


@bp.get("/papers/<int:paper_id>/keywords")
def keywords(paper_id: int):
    paper = Paper.query.get_or_404(paper_id)
    rows = paper.keywords.order_by(Keyword.score.desc()).all()
    return jsonify({"keywords": [k.to_dict() for k in rows]})


@bp.get("/topics")
def topics():
    return jsonify(library_topics())


@bp.post("/compare")
@limiter.limit("10/minute")
def compare():
    body = request.get_json(silent=True) or {}
    ids = body.get("paper_ids") or []
    if len(ids) != 2:
        return jsonify(error="bad_request", message="paper_ids must contain exactly two ids"), 400
    a = Paper.query.get(ids[0])
    b = Paper.query.get(ids[1])
    if not a or not b:
        return jsonify(error="not_found", message="One or both papers not found"), 404
    if a.status != "ready" or b.status != "ready":
        return jsonify(error="conflict", message="Both papers must be ready"), 409

    pack = {
        "paper_a": {
            "title": a.title,
            "abstract": a.abstract,
            "intro": _sec(a, "introduction"),
            "method": _sec(a, "methodology"),
            "results": _sec(a, "results"),
        },
        "paper_b": {
            "title": b.title,
            "abstract": b.abstract,
            "intro": _sec(b, "introduction"),
            "method": _sec(b, "methodology"),
            "results": _sec(b, "results"),
        },
    }
    schema = {
        "problem": {"a": "", "b": ""},
        "approach": {"a": "", "b": ""},
        "data": {"a": "", "b": ""},
        "results": {"a": "", "b": ""},
        "strengths": {"a": "", "b": ""},
        "weaknesses": {"a": "", "b": ""},
    }
    mode = "extractive"
    if llm.llm_configured():
        try:
            raw = llm.complete(
                "Compare two papers. Return ONLY JSON with keys problem, approach, data, "
                "results, strengths, weaknesses. Each value is {a, b} strings.",
                json.dumps(pack)[:24000],
                max_tokens=1500,
            )
            parsed = parse_json_loose(raw)
            schema = _normalize_compare(parsed)
            mode = "llm"
        except Exception:
            schema = _extractive_compare(a, b)
    else:
        schema = _extractive_compare(a, b)
    return jsonify(
        {
            "comparison": schema,
            "mode": mode,
            "llm_configured": llm.llm_configured(),
            "papers": [a.to_dict(), b.to_dict()],
        }
    )


def _sec(paper: Paper, name: str, n: int = 1800) -> str:
    s = paper.sections.filter_by(name=name).first()
    return (s.text or "")[:n] if s else ""


def _normalize_compare(obj: object) -> dict:
    keys = ("problem", "approach", "data", "results", "strengths", "weaknesses")
    out = {}
    if not isinstance(obj, dict):
        obj = {}
    for k in keys:
        v = obj.get(k, {})
        if isinstance(v, str):
            out[k] = {"a": v, "b": ""}
        elif isinstance(v, dict):
            out[k] = {"a": str(v.get("a") or v.get("paper_a") or ""), "b": str(v.get("b") or v.get("paper_b") or "")}
        else:
            out[k] = {"a": "", "b": ""}
    return out


def _extractive_compare(a: Paper, b: Paper) -> dict:
    def blurb(p: Paper) -> str:
        return (p.abstract or p.title or "")[:400]

    return {
        "problem": {"a": blurb(a), "b": blurb(b)},
        "approach": {"a": _sec(a, "methodology", 400), "b": _sec(b, "methodology", 400)},
        "data": {"a": _sec(a, "methodology", 200), "b": _sec(b, "methodology", 200)},
        "results": {"a": _sec(a, "results", 400), "b": _sec(b, "results", 400)},
        "strengths": {"a": "See abstract/results.", "b": "See abstract/results."},
        "weaknesses": {"a": "LLM not configured.", "b": "LLM not configured."},
    }
