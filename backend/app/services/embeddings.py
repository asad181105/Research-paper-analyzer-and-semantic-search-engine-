"""Singleton embedding model: batch encode + L2 normalize."""

from __future__ import annotations

import logging
import os
import threading
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None
_model_name: str | None = None
_dim: int | None = None


class HashingFallbackEncoder:
    """Deterministic bag-of-n-grams encoder used when transformers are unavailable."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def encode(self, texts, convert_to_numpy=True, normalize_embeddings=False, **kwargs):
        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = (text or "").lower().split()
            for tok in tokens:
                h = abs(hash(tok)) % self.dim
                vecs[i, h] += 1.0
                if len(tok) > 3:
                    vecs[i, abs(hash(tok[:3])) % self.dim] += 0.3
            n = np.linalg.norm(vecs[i])
            if n > 0:
                vecs[i] /= n
        return vecs


def get_model(model_name: str | None = None):
    """Load the sentence-transformer once per process."""
    global _model, _model_name, _dim
    name = model_name
    if name is None:
        try:
            from flask import current_app

            name = current_app.config.get(
                "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            )
        except RuntimeError:
            name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    with _lock:
        if _model is not None and _model_name == name:
            return _model
        logger.info("Loading embedding model: %s", name)
        force_hash = os.getenv("USE_HASH_EMBEDDINGS", "").lower() in {"1", "true", "yes"}
        if force_hash:
            _model = HashingFallbackEncoder(384)
            _dim = 384
            _model_name = name
            return _model
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(name)
            probe = _model.encode(["probe"], convert_to_numpy=True, normalize_embeddings=True)
            _dim = int(np.asarray(probe).shape[-1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falling back to hashing encoder: %s", exc)
            _model = HashingFallbackEncoder(384)
            _dim = 384
        _model_name = name
        return _model


def embedding_dim() -> int:
    if _dim is None:
        get_model()
    return int(_dim or 384)


def encode_texts(texts: Sequence[str], batch_size: int = 32) -> np.ndarray:
    model = get_model()
    if not texts:
        return np.zeros((0, embedding_dim()), dtype=np.float32)
    cleaned = [t if t else " " for t in texts]
    vecs = model.encode(
        list(cleaned),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    arr = np.asarray(vecs, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return l2_normalize(arr)


def encode_query(text: str) -> np.ndarray:
    return encode_texts([text])[0]


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return vectors.astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (vectors / norms).astype(np.float32)


def reset_model() -> None:
    global _model, _model_name, _dim
    with _lock:
        _model = None
        _model_name = None
        _dim = None


def warmup() -> None:
    if os.getenv("SKIP_EMBEDDING_WARMUP", "").lower() in {"1", "true", "yes"}:
        return
    try:
        get_model()
        encode_texts(["warmup"])
        logger.info("Embedding model ready (dim=%s)", embedding_dim())
    except Exception:
        logger.exception("Embedding warmup failed")
