import io

import fitz


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Tiny Paper On Retrieval", fontsize=16)
    page.insert_text((72, 120), "Abstract", fontsize=13)
    page.insert_text((72, 140), "This is an abstract about retrieval and ranking.", fontsize=11)
    page.insert_text((72, 200), "1 Introduction", fontsize=13)
    page.insert_text((72, 220), "We introduce the problem of scientific search.", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json["status"] == "ok"


def test_search_empty_query(client):
    r = client.get("/api/search?q=")
    assert r.status_code == 200
    assert r.json["results"] == []


def test_search_empty_library(client):
    r = client.get("/api/search?q=neural+retrieval")
    assert r.status_code == 200
    assert r.json["results"] == []


def test_topics_empty(client):
    r = client.get("/api/topics")
    assert r.status_code == 200


def test_qa_requires_question(client):
    r = client.post("/api/qa", json={})
    assert r.status_code == 400
    assert r.json["error"] == "bad_request"


def test_compare_validation(client):
    r = client.post("/api/compare", json={"paper_ids": [1]})
    assert r.status_code == 400


def test_upload_and_status(client, app):
    data = {"file": (io.BytesIO(_pdf_bytes()), "tiny.pdf")}
    r = client.post("/api/papers/upload", data=data, content_type="multipart/form-data")
    assert r.status_code in {200, 202}
    pid = r.json["paper"]["id"]
    st = client.get(f"/api/papers/{pid}/status")
    assert st.status_code == 200
    # run ingest synchronously in tests
    with app.app_context():
        from app.services.ingest import ingest_paper

        ingest_paper(pid)
    got = client.get(f"/api/papers/{pid}")
    assert got.status_code == 200
    assert got.json["status"] == "ready"
    sm = client.post(f"/api/papers/{pid}/summarize")
    assert sm.status_code == 200
    assert "tldr" in sm.json["summary"]
    kw = client.get(f"/api/papers/{pid}/keywords")
    assert kw.status_code == 200
    sim = client.get(f"/api/papers/{pid}/similar")
    assert sim.status_code == 200
    qa = client.post("/api/qa", json={"question": "What is this paper about?", "paper_id": pid})
    assert qa.status_code == 200
    assert "answer" in qa.json
    listing = client.get("/api/papers")
    assert listing.status_code == 200
    assert listing.json["total"] == 1
    sr = client.get("/api/search?q=retrieval&mode=hybrid")
    assert sr.status_code == 200
    deleted = client.delete(f"/api/papers/{pid}")
    assert deleted.status_code == 200
    gone = client.get(f"/api/papers/{pid}")
    assert gone.status_code == 404
