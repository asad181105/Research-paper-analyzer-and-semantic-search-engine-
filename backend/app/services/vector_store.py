"""FAISS IndexFlatIP with L2-normalized vectors, persisted to disk."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import faiss
import numpy as np

from app.services.embeddings import embedding_dim, l2_normalize

logger = logging.getLogger(__name__)
_lock = threading.Lock()


class FaissIndex:
    def __init__(self, path: Path, id_map_path: Path, dim: int | None = None):
        self.path = Path(path)
        self.id_map_path = Path(id_map_path)
        self.dim = dim or 384
        self.index = faiss.IndexFlatIP(self.dim)
        self.id_map: list[int] = []  # position -> entity id
        self._rev: dict[int, int] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.index = faiss.read_index(str(self.path))
                self.dim = int(self.index.d)
            except Exception:
                logger.exception("Failed to load FAISS index at %s; starting empty", self.path)
                self.index = faiss.IndexFlatIP(self.dim)
        if self.id_map_path.exists():
            try:
                self.id_map = json.loads(self.id_map_path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed to load id map")
                self.id_map = []
        self._rebuild_rev()

    def persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.path))
        self.id_map_path.write_text(json.dumps(self.id_map), encoding="utf-8")

    def _rebuild_rev(self) -> None:
        self._rev = {eid: i for i, eid in enumerate(self.id_map)}

    def add(self, entity_id: int, vector: np.ndarray) -> None:
        vec = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        if vec.shape[1] != self.index.d:
            raise ValueError(f"dim mismatch: {vec.shape[1]} vs {self.index.d}")
        vec = l2_normalize(vec)
        if entity_id in self._rev:
            self.delete([entity_id])
        self.index.add(vec)
        self.id_map.append(int(entity_id))
        self._rev[int(entity_id)] = len(self.id_map) - 1
        self.persist()

    def add_batch(self, entity_ids: list[int], vectors: np.ndarray) -> None:
        if len(entity_ids) == 0:
            return
        vecs = l2_normalize(np.asarray(vectors, dtype=np.float32))
        if vecs.shape[1] != self.index.d:
            raise ValueError("dim mismatch")
        existing = [eid for eid in entity_ids if eid in self._rev]
        if existing:
            self.delete(existing)
        self.index.add(vecs)
        start = len(self.id_map)
        for i, eid in enumerate(entity_ids):
            self.id_map.append(int(eid))
            self._rev[int(eid)] = start + i
        self.persist()

    def search(self, query: np.ndarray, k: int = 10) -> list[tuple[int, float]]:
        if self.index.ntotal == 0:
            return []
        q = l2_normalize(np.asarray(query, dtype=np.float32).reshape(1, -1))
        k = max(1, min(k, self.index.ntotal))
        scores, idxs = self.index.search(q, k)
        out: list[tuple[int, float]] = []
        for score, ix in zip(scores[0], idxs[0], strict=False):
            if ix < 0 or ix >= len(self.id_map):
                continue
            out.append((int(self.id_map[ix]), float(score)))
        return out

    def delete(self, entity_ids: list[int]) -> None:
        remove = {int(e) for e in entity_ids}
        if not remove.intersection(self._rev):
            return
        keep_pos = [i for i, eid in enumerate(self.id_map) if eid not in remove]
        if not keep_pos:
            self.index = faiss.IndexFlatIP(self.dim)
            self.id_map = []
            self._rev = {}
            self.persist()
            return
        vectors = self.index.reconstruct_n(0, self.index.ntotal)
        kept = np.asarray(vectors, dtype=np.float32)[keep_pos]
        new_index = faiss.IndexFlatIP(self.dim)
        new_index.add(kept)
        self.index = new_index
        self.id_map = [self.id_map[i] for i in keep_pos]
        self._rebuild_rev()
        self.persist()

    def rebuild(self, entity_ids: list[int], vectors: np.ndarray) -> None:
        self.dim = int(np.asarray(vectors).shape[1]) if len(entity_ids) else self.dim
        self.index = faiss.IndexFlatIP(self.dim)
        self.id_map = []
        self._rev = {}
        if entity_ids:
            self.add_batch(entity_ids, vectors)

    def ntotal(self) -> int:
        return int(self.index.ntotal)


class VectorStore:
    """Holds chunk-level and paper-level FAISS indexes."""

    def __init__(self, data_dir: Path):
        idx_dir = Path(data_dir) / "indexes"
        idx_dir.mkdir(parents=True, exist_ok=True)
        dim = 384
        try:
            dim = embedding_dim()
        except Exception:
            dim = 384
        self.chunks = FaissIndex(idx_dir / "chunks.faiss", idx_dir / "chunks_ids.json", dim)
        self.papers = FaissIndex(idx_dir / "papers.faiss", idx_dir / "papers_ids.json", dim)

    def persist(self) -> None:
        with _lock:
            self.chunks.persist()
            self.papers.persist()


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    from flask import current_app

    if _store is None:
        _store = VectorStore(Path(current_app.config["DATA_DIR"]))
        # Align dim if empty indexes were created with default 384
        dim = embedding_dim()
        if _store.chunks.index.ntotal == 0 and _store.chunks.dim != dim:
            _store.chunks = FaissIndex(
                _store.chunks.path, _store.chunks.id_map_path, dim
            )
            _store.papers = FaissIndex(
                _store.papers.path, _store.papers.id_map_path, dim
            )
    return _store


def reset_vector_store() -> None:
    global _store
    _store = None
