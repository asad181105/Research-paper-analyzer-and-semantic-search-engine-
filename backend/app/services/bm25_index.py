"""BM25 over chunks; rebuilt on library changes and persisted as a token cache."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_instance: "BM25Store | None" = None


def tokenize(text: str) -> list[str]:
    return [t for t in (text or "").lower().split() if t]


class BM25Store:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "indexes" / "bm25.json"
        self.ids: list[int] = []
        self.corpus_tokens: list[list[str]] = []
        self.bm25: BM25Okapi | None = None
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                self.ids = [int(x) for x in payload.get("ids", [])]
                self.corpus_tokens = payload.get("tokens", [])
                if self.corpus_tokens:
                    self.bm25 = BM25Okapi(self.corpus_tokens)
            except Exception:
                logger.exception("Failed to load BM25 cache")

    def persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"ids": self.ids, "tokens": self.corpus_tokens}),
            encoding="utf-8",
        )

    def rebuild_from_pairs(self, pairs: list[tuple[int, str]]) -> None:
        self.ids = [int(i) for i, _ in pairs]
        self.corpus_tokens = [tokenize(t) for _, t in pairs]
        self.bm25 = BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None
        self.persist()

    def add(self, chunk_id: int, text: str) -> None:
        if chunk_id in self.ids:
            self.delete([chunk_id])
        self.ids.append(int(chunk_id))
        self.corpus_tokens.append(tokenize(text))
        self.bm25 = BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None

    def add_many(self, pairs: list[tuple[int, str]]) -> None:
        for cid, text in pairs:
            self.add(cid, text)
        self.persist()

    def delete(self, chunk_ids: list[int]) -> None:
        remove = {int(x) for x in chunk_ids}
        kept_ids = []
        kept_toks = []
        for cid, toks in zip(self.ids, self.corpus_tokens, strict=False):
            if cid not in remove:
                kept_ids.append(cid)
                kept_toks.append(toks)
        self.ids = kept_ids
        self.corpus_tokens = kept_toks
        self.bm25 = BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None
        self.persist()

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        if not self.bm25 or not self.ids:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        max_s = max((s for _, s in ranked), default=1.0) or 1.0
        out = []
        for i, s in ranked:
            if s <= 0:
                continue
            out.append((self.ids[i], float(s / max_s)))
        return out


def get_bm25() -> BM25Store:
    global _instance
    from flask import current_app

    if _instance is None:
        _instance = BM25Store(Path(current_app.config["DATA_DIR"]))
        if not _instance.ids:
            from app.models import Chunk

            pairs = [(c.id, c.text) for c in Chunk.query.all()]
            if pairs:
                _instance.rebuild_from_pairs(pairs)
    return _instance


def reset_bm25() -> None:
    global _instance
    _instance = None
