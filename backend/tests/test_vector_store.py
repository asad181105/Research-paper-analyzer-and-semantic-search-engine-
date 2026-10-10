import numpy as np

from app.services.embeddings import l2_normalize
from app.services.vector_store import FaissIndex


def test_faiss_add_search_delete(tmp_path):
    idx = FaissIndex(tmp_path / "t.faiss", tmp_path / "ids.json", dim=8)
    rng = np.random.default_rng(0)
    a = l2_normalize(rng.normal(size=(1, 8)).astype(np.float32))[0]
    b = l2_normalize(rng.normal(size=(1, 8)).astype(np.float32))[0]
    idx.add(10, a)
    idx.add(20, b)
    idx.persist()
    hits = idx.search(a, k=2)
    assert hits[0][0] == 10
    assert hits[0][1] > 0.99
    idx.delete([10])
    hits2 = idx.search(a, k=2)
    assert all(h[0] != 10 for h in hits2)
    assert idx.ntotal() == 1
    idx2 = FaissIndex(tmp_path / "t.faiss", tmp_path / "ids.json", dim=8)
    assert idx2.ntotal() == 1
