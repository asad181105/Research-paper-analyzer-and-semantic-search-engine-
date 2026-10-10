"""Rebuild FAISS and BM25 from the SQLite database.

Usage (from backend/):
    python -m app.scripts.rebuild_index
"""

from __future__ import annotations

import logging

import numpy as np

from app import create_app
from app.models import Chunk, Paper
from app.services.bm25_index import get_bm25
from app.services.embeddings import encode_texts, embedding_dim
from app.services.vector_store import get_vector_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rebuild_index")


def rebuild() -> None:
    app = create_app()
    with app.app_context():
        store = get_vector_store()
        dim = embedding_dim()
        chunks = Chunk.query.all()
        if chunks:
            store.chunks.rebuild([c.id for c in chunks], encode_texts([c.text for c in chunks]))
        else:
            store.chunks.rebuild([], np.zeros((0, dim), dtype=np.float32))
        papers = Paper.query.filter_by(status="ready").all()
        if papers:
            store.papers.rebuild(
                [p.id for p in papers],
                encode_texts([(p.title or "") + "\n" + (p.abstract or "") for p in papers]),
            )
        else:
            store.papers.rebuild([], np.zeros((0, dim), dtype=np.float32))
        store.persist()
        get_bm25().rebuild_from_pairs([(c.id, c.text) for c in chunks])
        logger.info("Rebuilt %s chunks and %s papers", len(chunks), len(papers))


if __name__ == "__main__":
    rebuild()
