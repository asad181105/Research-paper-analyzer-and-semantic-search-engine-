from flask import Blueprint, Response, jsonify, request, stream_with_context

from app.extensions import limiter
from app.models import Paper, QAHistory
from app.services.rag import answer_question, stream_answer

bp = Blueprint("qa", __name__)


@bp.post("/qa")
@limiter.limit("20/minute")
def qa():
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify(error="bad_request", message="question is required"), 400
    paper_id = body.get("paper_id")
    if paper_id is not None:
        Paper.query.get_or_404(paper_id)
    stream = str(request.args.get("stream") or body.get("stream") or "").lower() in {
        "1",
        "true",
        "yes",
    }
    if stream:
        return Response(
            stream_with_context(stream_answer(question, paper_id=paper_id)),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    result = answer_question(question, paper_id=paper_id)
    return jsonify(result)


@bp.get("/qa/stream")
@limiter.limit("20/minute")
def qa_stream():
    question = (request.args.get("question") or "").strip()
    if not question:
        return jsonify(error="bad_request", message="question is required"), 400
    paper_id = request.args.get("paper_id")
    pid = int(paper_id) if paper_id else None
    if pid:
        Paper.query.get_or_404(pid)
    return Response(
        stream_with_context(stream_answer(question, paper_id=pid)),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.get("/qa/history")
def history():
    paper_id = request.args.get("paper_id")
    q = QAHistory.query.order_by(QAHistory.created_at.desc())
    if paper_id:
        q = q.filter_by(paper_id=int(paper_id))
    rows = q.limit(50).all()
    return jsonify({"history": [r.to_dict() for r in rows]})
