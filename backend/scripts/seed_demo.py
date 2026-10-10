"""Download a demo corpus of NLP/IR papers from arXiv and ingest them.

Run from backend/:
    python scripts/seed_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Paper  # noqa: E402
from app.services.arxiv_client import search_arxiv  # noqa: E402
from app.services.ingest import import_from_arxiv, ingest_paper  # noqa: E402

QUERIES = [
    "ti:Attention Is All You Need",
    "ti:BERT: Pre-training of Deep Bidirectional Transformers",
    "ti:Dense Passage Retrieval",
    "ti:ColBERT",
    "ti:Sentence-BERT",
    "information retrieval neural ranking",
    "cat:cs.CL AND dense retrieval",
    "cat:cs.IR AND semantic search",
    "question answering retrieval",
    "scientific document summarization",
]


def main() -> None:
    app = create_app()
    seen: set[str] = set()
    ids: list[str] = []
    with app.app_context():
        for q in QUERIES:
            try:
                hits = search_arxiv(q, max_results=5)
            except Exception as exc:  # noqa: BLE001
                print("search failed", q, exc)
                continue
            for h in hits:
                aid = h["arxiv_id"]
                if aid in seen:
                    continue
                seen.add(aid)
                ids.append(aid)
                if len(ids) >= 30:
                    break
            if len(ids) >= 30:
                break
        print(f"Importing {len(ids)} papers…")
        for aid in ids:
            existing = Paper.query.filter_by(arxiv_id=aid).first()
            if existing:
                print("skip existing", aid)
                continue
            try:
                paper = import_from_arxiv(aid)
                ingest_paper(paper.id)
                print("ready", aid, paper.title[:80])
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                print("failed", aid, exc)
        print("Library size:", Paper.query.filter_by(status="ready").count())


if __name__ == "__main__":
    main()
