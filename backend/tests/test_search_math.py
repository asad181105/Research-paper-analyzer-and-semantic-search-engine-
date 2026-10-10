from app.services.search_engine import citation_boost, reciprocal_rank_fusion


def test_rrf_prefers_consensus():
    a = [(1, 0.9), (2, 0.8), (3, 0.1)]
    b = [(2, 0.9), (1, 0.5), (4, 0.4)]
    fused = reciprocal_rank_fusion([a, b], k=60)
    # id 1 and 2 appear in both lists; 2 is rank 2 + rank 1 vs 1 is rank 1 + rank 2 — close
    assert fused[1] > fused[3]
    assert fused[2] > fused[4]


def test_citation_boost_weights():
    low = citation_boost(1.0, 0, cit_w=0.15, rel_w=0.85)
    high = citation_boost(1.0, 5000, cit_w=0.15, rel_w=0.85)
    assert 0.84 < low < 0.86
    assert high > low
    assert high <= 1.0001
