"""Hybrid retrieval: FAISS + BM25 with Reciprocal Rank Fusion and citation boost."""

from __future__ import annotations

import math
from collections import defaultdict

from flask import current_app

from app.models import Chunk, Paper
from app.services.bm25_index import get_bm25
from app.services.embeddings import encode_query
from app.services.vector_store import get_vector_store
from app.utils.text import highlight_passage


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[int, float]]], k: int = 60
) -> dict[int, float]:
    scores: dict[int, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, (eid, _s) in enumerate(ranked, start=1):
            scores[eid] += 1.0 / (k + rank)
    return dict(scores)


def citation_boost(relevance: float, citation_count: int, cit_w: float, rel_w: float) -> float:
    cit = math.log1p(max(citation_count, 0))
    # normalize log citations into 0..1 with a soft cap at ~10000 cites
    cit_norm = min(cit / math.log1p(10000), 1.0)
    return rel_w * relevance + cit_w * cit_norm


def aggregate_chunk_scores(chunk_scores: dict[int, float]) -> dict[int, dict]:
    """Map chunk RRF scores to papers: max + small bonus for extra matches."""
    chunks = Chunk.query.filter(Chunk.id.in_(list(chunk_scores.keys()) or [0])).all()
    by_id = {c.id: c for c in chunks}
    papers: dict[int, dict] = {}
    for cid, score in chunk_scores.items():
        ch = by_id.get(cid)
        if not ch:
            continue
        rec = papers.setdefault(
            ch.paper_id,
            {"max": 0.0, "sum": 0.0, "count": 0, "best_chunk": ch, "best_score": -1.0},
        )
        rec["sum"] += score
        rec["count"] += 1
        rec["max"] = max(rec["max"], score)
        if score > rec["best_score"]:
            rec["best_score"] = score
            rec["best_chunk"] = ch
    for rec in papers.values():
        rec["paper_score"] = rec["max"] + 0.05 * max(rec["count"] - 1, 0)
    return papers


def search(
    query: str,
    k: int = 10,
    mode: str = "hybrid",
    section: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    author: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    query = (query or "").strip()
    if not query:
        return {"results": [], "total": 0, "page": page, "page_size": page_size, "query": query}
    if Paper.query.filter_by(status="ready").count() == 0:
        return {
            "results": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "query": query,
            "message": "Library is empty",
        }

    pool = max(k * 8, 40)
    faiss_hits: list[tuple[int, float]] = []
    bm25_hits: list[tuple[int, float]] = []

    if mode in {"semantic", "hybrid"}:
        qv = encode_query(query)
        faiss_hits = get_vector_store().chunks.search(qv, k=pool)
    if mode in {"keyword", "hybrid"}:
        bm25_hits = get_bm25().search(query, k=pool)

    if mode == "semantic":
        chunk_scores = {cid: s for cid, s in faiss_hits}
    elif mode == "keyword":
        chunk_scores = {cid: s for cid, s in bm25_hits}
    else:
        chunk_scores = reciprocal_rank_fusion([faiss_hits, bm25_hits])

    paper_agg = aggregate_chunk_scores(chunk_scores)
    cit_w = float(current_app.config.get("CITATION_WEIGHT", 0.15))
    rel_w = float(current_app.config.get("RELEVANCE_WEIGHT", 0.85))
    max_ps = max((r["paper_score"] for r in paper_agg.values()), default=1.0) or 1.0

    results = []
    for pid, rec in paper_agg.items():
        paper = Paper.query.get(pid)
        if not paper or paper.status != "ready":
            continue
        if section and rec["best_chunk"].section_name != section:
            continue
        if year_from and (paper.year or 0) < year_from:
            continue
        if year_to and (paper.year or 9999) > year_to:
            continue
        if author and author.lower() not in (paper.authors or "").lower():
            continue
        rel = rec["paper_score"] / max_ps
        cites = paper.citation_count or 0
        final = citation_boost(rel, cites, cit_w, rel_w)
        ch = rec["best_chunk"]
        results.append(
            {
                "paper": paper.to_dict(),
                "passage": highlight_passage(ch.text, query),
                "passage_raw": ch.text,
                "section": ch.section_name,
                "page": ch.page,
                "chunk_id": ch.id,
                "scores": {
                    "relevance": round(rel, 4),
                    "citation_count": cites,
                    "final": round(final, 4),
                    "rrf_chunk": round(rec["best_score"], 4),
                },
                "citation_count": cites,
                "score": round(final, 4),
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    total = len(results)
    start = max(page - 1, 0) * page_size
    sliced = results[start : start + page_size]
    return {
        "results": sliced,
        "total": total,
        "page": page,
        "page_size": page_size,
        "query": query,
        "mode": mode,
    }


def similar_papers(paper_id: int, k: int = 5) -> list[dict]:
    store = get_vector_store()
    hits = store.papers.search_by_id(paper_id, k=k + 1) if hasattr(store.papers, "search_by_id") else None
    if hits is None:
        # reconstruct vector for this paper
        pos = store.papers._rev.get(paper_id)
        if pos is None:
            return []
        vec = store.papers.index.reconstruct(pos)
        hits = store.papers.search(vec, k=k + 1)
    out = []
    for pid, score in hits:
        if pid == paper_id:
            continue
        paper = Paper.query.get(pid)
        if paper and paper.status == "ready":
            out.append({"paper": paper.to_dict(), "score": round(float(score), 4)})
        if len(out) >= k:
            break
    return out
