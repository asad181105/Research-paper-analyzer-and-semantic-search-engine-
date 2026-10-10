"""KeyBERT keywords per paper and KMeans topic clusters over the library."""

from __future__ import annotations

import logging

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from app.extensions import db
from app.models import Keyword, Paper
from app.services.embeddings import encode_texts
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def extract_keywords(text: str, top_n: int = 8) -> list[tuple[str, float]]:
    text = (text or "").strip()
    if len(text) < 40:
        return []
    try:
        from keybert import KeyBERT
        from keybert.backend import BaseEmbedder

        class SharedEmbedder(BaseEmbedder):
            def embed(self, documents, verbose: bool = False):
                return encode_texts(list(documents))

        kw_model = KeyBERT(model=SharedEmbedder())
        pairs = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            top_n=top_n,
            use_mmr=True,
            diversity=0.5,
        )
        return [(str(k), float(s)) for k, s in pairs]
    except Exception:
        logger.exception("KeyBERT failed; using frequency fallback")
        return _freq_keywords(text, top_n)


def _freq_keywords(text: str, top_n: int) -> list[tuple[str, float]]:
    stop = {
        "the", "and", "for", "that", "with", "this", "from", "are", "was", "were",
        "have", "has", "not", "but", "our", "can", "use", "using", "used", "based",
        "paper", "also", "which", "these", "than", "into", "such", "their",
    }
    counts: dict[str, int] = {}
    words = [w.strip(".,;:()[]").lower() for w in text.split()]
    for w in words:
        if len(w) < 4 or w in stop or not w.isalpha():
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not ranked:
        return []
    m = ranked[0][1]
    return [(k, round(v / m, 4)) for k, v in ranked]


def store_keywords(paper: Paper, text: str) -> list[Keyword]:
    Keyword.query.filter_by(paper_id=paper.id).delete()
    rows = []
    for term, score in extract_keywords(text, 8):
        row = Keyword(paper_id=paper.id, keyword=term, score=score)
        db.session.add(row)
        rows.append(row)
    return rows


def library_topics() -> dict:
    papers = Paper.query.filter_by(status="ready").all()
    if len(papers) < 2:
        return {"clusters": [], "points": [], "k": 0, "message": "Need at least 2 ready papers"}

    store = get_vector_store()
    ids, vecs = [], []
    for p in papers:
        pos = store.papers._rev.get(p.id)
        if pos is None:
            continue
        ids.append(p.id)
        vecs.append(store.papers.index.reconstruct(pos))
    if len(ids) < 2:
        # embed title+abstract on the fly
        ids = [p.id for p in papers]
        vecs = encode_texts([(p.title or "") + " " + (p.abstract or "") for p in papers])
    X = np.asarray(vecs, dtype=np.float32)
    k = _choose_k(X, cap=8)
    labels = np.zeros(len(ids), dtype=int)
    if k >= 2:
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(X)
    else:
        k = 1

    coords = _project2d(X)
    paper_by_id = {p.id: p for p in papers}
    clusters = []
    for c in range(k):
        members = [ids[i] for i in range(len(ids)) if int(labels[i]) == c]
        kws = []
        for pid in members:
            kws.extend([kw.keyword for kw in paper_by_id[pid].keywords.all()])
        label = ", ".join(_top_terms(kws, 4)) or f"Topic {c + 1}"
        clusters.append({"id": c, "label": label, "paper_ids": members, "size": len(members)})

    points = []
    for i, pid in enumerate(ids):
        p = paper_by_id[pid]
        points.append(
            {
                "paper_id": pid,
                "title": p.title,
                "x": float(coords[i, 0]),
                "y": float(coords[i, 1]),
                "cluster": int(labels[i]),
            }
        )
    return {"clusters": clusters, "points": points, "k": k}


def _choose_k(X: np.ndarray, cap: int = 8) -> int:
    n = len(X)
    if n < 3:
        return 1 if n else 0
    best_k, best_s = 2, -1.0
    for k in range(2, min(cap, n - 1) + 1):
        try:
            labels = KMeans(n_clusters=k, n_init=8, random_state=42).fit_predict(X)
            if len(set(labels)) < 2:
                continue
            s = silhouette_score(X, labels)
            if s > best_s:
                best_s, best_k = s, k
        except Exception:
            continue
    return best_k


def _project2d(X: np.ndarray) -> np.ndarray:
    try:
        import umap

        reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=min(8, len(X) - 1))
        return np.asarray(reducer.fit_transform(X), dtype=np.float32)
    except Exception:
        pca = PCA(n_components=2, random_state=42)
        return np.asarray(pca.fit_transform(X), dtype=np.float32)


def _top_terms(terms: list[str], n: int) -> list[str]:
    counts: dict[str, int] = {}
    for t in terms:
        counts[t] = counts.get(t, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]]
