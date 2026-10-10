"""Compare BM25 vs semantic vs hybrid retrieval on a labeled query set.

Writes evaluation_results.csv next to this script (or DATA_DIR).
Run from backend/:
    python scripts/evaluate.py
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.models import Paper  # noqa: E402
from app.services.search_engine import search  # noqa: E402

# Queries with keywords that should match seeded NLP/IR papers.
# Relevance is judged by title/abstract term overlap with the listed stems
# plus explicit title keywords. This is automatic over whatever corpus is present.
QUERY_STEMS = [
    ("transformer attention encoder decoder", ["attention", "transformer", "encoder"]),
    ("bidirectional transformer language model pretraining", ["bert", "language model", "pretrain"]),
    ("dense passage retrieval dual encoder", ["dense", "passage", "retrieval", "dpr"]),
    ("late interaction token embeddings ranking", ["colbert", "late interaction"]),
    ("sentence embeddings siamese bert", ["sentence", "sbert", "siamese"]),
    ("bm25 lexical retrieval baseline", ["bm25", "lexical"]),
    ("semantic search scientific papers", ["semantic", "scientific", "search"]),
    ("neural ranking learning to rank documents", ["ranking", "neural"]),
    ("question answering open domain retrieval", ["question answering", "retrieval"]),
    ("document summarization abstractive", ["summar"]),
    ("information retrieval evaluation ndcg", ["ndcg", "evaluation"]),
    ("vector similarity cosine embeddings", ["embedding", "vector", "cosine"]),
    ("hybrid sparse dense retrieval fusion", ["hybrid", "dense", "sparse"]),
    ("citation network scholarly papers", ["citation", "scholar"]),
    ("named entity recognition sequence labeling", ["entity", "ner"]),
    ("machine translation sequence to sequence", ["translation", "sequence"]),
    ("contrastive learning representations", ["contrastive"]),
    ("reranking cross encoder", ["rerank", "cross-encoder", "cross encoder"]),
    ("topic modeling clustering documents", ["topic", "cluster"]),
    ("query expansion pseudo relevance feedback", ["query expansion", "feedback"]),
]


def relevant_ids(papers: list[Paper], stems: list[str]) -> set[int]:
    rel = set()
    for p in papers:
        blob = f"{p.title} {p.abstract}".lower()
        if any(s.lower() in blob for s in stems):
            rel.add(p.id)
    return rel


def metrics_at(ranked_ids: list[int], relevant: set[int], p_at=5, r_at=10, ndcg_at=10) -> dict:
    if not relevant:
        return {"p@5": 0.0, "r@10": 0.0, "mrr": 0.0, "ndcg@10": 0.0}
    hits5 = sum(1 for i in ranked_ids[:p_at] if i in relevant)
    hits10 = sum(1 for i in ranked_ids[:r_at] if i in relevant)
    p5 = hits5 / p_at
    r10 = hits10 / len(relevant)
    mrr = 0.0
    for rank, pid in enumerate(ranked_ids, start=1):
        if pid in relevant:
            mrr = 1.0 / rank
            break
    dcg = 0.0
    for i, pid in enumerate(ranked_ids[:ndcg_at], start=1):
        rel = 1.0 if pid in relevant else 0.0
        dcg += rel / math.log2(i + 1)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), ndcg_at) + 1))
    ndcg = dcg / ideal if ideal else 0.0
    return {"p@5": p5, "r@10": r10, "mrr": mrr, "ndcg@10": ndcg}


def evaluate_mode(mode: str, papers: list[Paper]) -> dict:
    agg = defaultdict(float)
    n = 0
    for query, stems in QUERY_STEMS:
        rel = relevant_ids(papers, stems)
        res = search(query, k=10, mode=mode, page=1, page_size=10)
        ranked = [r["paper"]["id"] for r in res.get("results", [])]
        m = metrics_at(ranked, rel)
        for k, v in m.items():
            agg[k] += v
        n += 1
    return {k: (agg[k] / n if n else 0.0) for k in ("p@5", "r@10", "mrr", "ndcg@10")}


def main() -> None:
    app = create_app()
    out_path = ROOT / "evaluation_results.csv"
    with app.app_context():
        papers = Paper.query.filter_by(status="ready").all()
        if len(papers) < 3:
            print("Need a seeded library (python scripts/seed_demo.py) before evaluation.")
            sys.exit(1)
        rows = []
        print(f"{'mode':<12} {'P@5':>8} {'R@10':>8} {'MRR':>8} {'nDCG@10':>8}")
        for mode in ("keyword", "semantic", "hybrid"):
            m = evaluate_mode(mode, papers)
            print(f"{mode:<12} {m['p@5']:8.3f} {m['r@10']:8.3f} {m['mrr']:8.3f} {m['ndcg@10']:8.3f}")
            rows.append({"mode": mode, **m})
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["mode", "p@5", "r@10", "mrr", "ndcg@10"])
            w.writeheader()
            w.writerows(rows)
        print("Wrote", out_path)


if __name__ == "__main__":
    main()
