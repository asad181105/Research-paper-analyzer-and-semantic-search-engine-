"""Retrieval-augmented QA with source citations and optional streaming."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from app.extensions import db
from app.models import Chunk, Paper, QAHistory
from app.services import llm
from app.services.bm25_index import get_bm25
from app.services.embeddings import encode_query
from app.services.search_engine import reciprocal_rank_fusion
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

SYSTEM = (
    "You are a careful research assistant. Answer ONLY using the numbered context "
    "passages. Cite sources inline as [1], [2], matching the passage numbers. "
    "If the answer is not in the context, reply exactly: not found in the paper. "
    "Do not invent citations or facts."
)


def retrieve_chunks(question: str, paper_id: int | None = None, k: int = 8) -> list[dict]:
    qv = encode_query(question)
    store = get_vector_store()
    faiss_hits = store.chunks.search(qv, k=40)
    bm25_hits = get_bm25().search(question, k=40)

    if paper_id:
        allowed = {c.id for c in Chunk.query.filter_by(paper_id=paper_id).all()}
        faiss_hits = [(i, s) for i, s in faiss_hits if i in allowed]
        bm25_hits = [(i, s) for i, s in bm25_hits if i in allowed]

    fused = reciprocal_rank_fusion([faiss_hits, bm25_hits])
    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    sources = []
    for cid, score in ranked:
        ch = Chunk.query.get(cid)
        if not ch:
            continue
        paper = Paper.query.get(ch.paper_id)
        if not paper:
            continue
        sources.append(
            {
                "chunk_id": ch.id,
                "paper_id": paper.id,
                "paper_title": paper.title,
                "section": ch.section_name,
                "page": ch.page,
                "snippet": ch.text[:500],
                "score": round(float(score), 4),
            }
        )
        if len(sources) >= k:
            break
    return sources


def build_user_prompt(question: str, sources: list[dict], history: list[QAHistory] | None = None) -> str:
    ctx_lines = []
    for i, s in enumerate(sources, start=1):
        ctx_lines.append(
            f"[{i}] {s['paper_title']} | {s['section']} | p.{s['page']}\n{s['snippet']}"
        )
    hist = ""
    if history:
        turns = []
        for h in history[-3:]:
            turns.append(f"User: {h.question}\nAssistant: {h.answer}")
        hist = "Previous turns:\n" + "\n".join(turns) + "\n\n"
    return hist + "Context:\n" + "\n\n".join(ctx_lines) + f"\n\nQuestion: {question}"


def answer_question(question: str, paper_id: int | None = None) -> dict:
    sources = retrieve_chunks(question, paper_id=paper_id, k=8)
    history = []
    q = QAHistory.query
    if paper_id:
        q = q.filter_by(paper_id=paper_id)
    else:
        q = q.filter(QAHistory.paper_id.is_(None))
    history = q.order_by(QAHistory.created_at.desc()).limit(3).all()[::-1]

    fallback_answer = _fallback_answer(sources)
    used_llm = False
    if llm.llm_configured() and sources:
        try:
            raw = llm.complete(SYSTEM, build_user_prompt(question, sources, history), max_tokens=800)
            answer = raw.strip()
            used_llm = True
        except Exception:
            logger.exception("LLM QA failed")
            answer = fallback_answer
    else:
        answer = fallback_answer if sources else "not found in the paper"

    rec = QAHistory(
        paper_id=paper_id,
        question=question,
        answer=answer,
        sources_json=json.dumps(sources),
    )
    db.session.add(rec)
    db.session.commit()
    return {
        "id": rec.id,
        "answer": answer,
        "sources": sources,
        "mode": "llm" if used_llm else "retrieval",
        "llm_configured": llm.llm_configured(),
    }


def stream_answer(question: str, paper_id: int | None = None) -> Iterator[str]:
    sources = retrieve_chunks(question, paper_id=paper_id, k=8)
    history = []
    q = QAHistory.query
    if paper_id:
        q = q.filter_by(paper_id=paper_id)
    else:
        q = q.filter(QAHistory.paper_id.is_(None))
    history = q.order_by(QAHistory.created_at.desc()).limit(3).all()[::-1]

    yield f"event: sources\ndata: {json.dumps(sources)}\n\n"

    if not llm.llm_configured() or not sources:
        answer = _fallback_answer(sources) if sources else "not found in the paper"
        yield f"event: token\ndata: {json.dumps(answer)}\n\n"
        rec = QAHistory(
            paper_id=paper_id, question=question, answer=answer, sources_json=json.dumps(sources)
        )
        db.session.add(rec)
        db.session.commit()
        yield f"event: done\ndata: {json.dumps({'id': rec.id, 'mode': 'retrieval'})}\n\n"
        return

    buf: list[str] = []
    try:
        for tok in llm.stream_complete(SYSTEM, build_user_prompt(question, sources, history)):
            buf.append(tok)
            yield f"event: token\ndata: {json.dumps(tok)}\n\n"
    except Exception:
        logger.exception("stream failed")
        msg = _fallback_answer(sources)
        buf = [msg]
        yield f"event: token\ndata: {json.dumps(msg)}\n\n"
    answer = "".join(buf)
    rec = QAHistory(
        paper_id=paper_id, question=question, answer=answer, sources_json=json.dumps(sources)
    )
    db.session.add(rec)
    db.session.commit()
    yield f"event: done\ndata: {json.dumps({'id': rec.id, 'mode': 'llm'})}\n\n"


def _fallback_answer(sources: list[dict]) -> str:
    if not sources:
        return "not found in the paper"
    lines = ["LLM is not configured. Top retrieved passages:", ""]
    for i, s in enumerate(sources[:5], start=1):
        lines.append(f"[{i}] ({s['paper_title']}, {s['section']}, p.{s['page']}) {s['snippet'][:280]}")
    return "\n".join(lines)
