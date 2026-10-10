"""Background ingestion: parse -> chunk -> embed -> index -> keywords -> citations."""

from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path

from flask import Flask, current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Chunk, Keyword, Paper, QAHistory, Section
from app.services.arxiv_client import download_pdf
from app.services.bm25_index import get_bm25
from app.services.chunker import chunk_paper
from app.services.citations import lookup_citations
from app.services.embeddings import encode_texts
from app.services.keywords import store_keywords
from app.services.pdf_parser import parse_pdf
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)
ALLOWED_MIMES = {"application/pdf", "application/x-pdf", "application/octet-stream"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_upload(file_storage, max_mb: int) -> None:
    filename = secure_filename(file_storage.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are accepted")
    mime = (file_storage.mimetype or "").lower()
    if mime and mime not in ALLOWED_MIMES and not mime.endswith("/pdf"):
        raise ValueError(f"Unsupported MIME type: {mime}")
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {max_mb} MB limit")
    if size < 64:
        raise ValueError("File is empty or too small to be a PDF")
    header = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    if header != b"%PDF-":
        raise ValueError("File is not a valid PDF")


def save_upload(file_storage, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = secure_filename(file_storage.filename or "upload.pdf")
    path = dest_dir / name
    i = 1
    while path.exists():
        path = dest_dir / f"{path.stem}_{i}.pdf"
        i += 1
    file_storage.save(str(path))
    return path


def create_paper_record(**kwargs) -> Paper:
    paper = Paper(**kwargs)
    db.session.add(paper)
    db.session.commit()
    return paper


def schedule_ingest(app: Flask, paper_id: int) -> None:
    if app.config.get("TESTING"):
        return
    t = threading.Thread(target=_run_ingest, args=(app, paper_id), daemon=True)
    t.start()


def _run_ingest(app: Flask, paper_id: int) -> None:
    with app.app_context():
        try:
            ingest_paper(paper_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ingestion failed for paper %s", paper_id)
            paper = Paper.query.get(paper_id)
            if paper:
                paper.status = "failed"
                paper.status_message = str(exc)[:1000]
                db.session.commit()


def ingest_paper(paper_id: int) -> None:
    paper = Paper.query.get(paper_id)
    if not paper:
        return
    paper.status = "processing"
    paper.progress = 5
    paper.status_message = "Parsing PDF"
    db.session.commit()

    path = Path(paper.file_path)
    parsed = parse_pdf(str(path))

    paper.title = paper.title or parsed.title
    if parsed.title and (not paper.title or paper.title == "Untitled"):
        paper.title = parsed.title
    if parsed.authors and not paper.authors:
        paper.authors = parsed.authors
    if parsed.abstract:
        paper.abstract = parsed.abstract
    if parsed.year and not paper.year:
        paper.year = parsed.year

    paper.progress = 25
    paper.status_message = "Saving sections"
    # replace sections/chunks
    paper.sections.delete()
    paper.chunks.delete()
    db.session.commit()

    section_rows: list[Section] = []
    for sec in parsed.sections:
        row = Section(
            paper_id=paper.id,
            name=sec.name,
            title_raw=sec.title_raw,
            text=sec.text,
            page_start=sec.page_start,
            page_end=sec.page_end,
            order=sec.order,
        )
        db.session.add(row)
        section_rows.append(row)
    db.session.commit()

    paper.progress = 40
    paper.status_message = "Chunking"
    db.session.commit()

    from flask import current_app

    target = int(current_app.config.get("CHUNK_TOKENS", 300))
    overlap = int(current_app.config.get("CHUNK_OVERLAP", 50))
    pieces = chunk_paper(parsed, target_tokens=target, overlap=overlap)
    name_to_section = {s.name: s for s in section_rows}
    chunk_rows: list[Chunk] = []
    for p in pieces:
        sec = name_to_section.get(p.section_name)
        row = Chunk(
            paper_id=paper.id,
            section_id=sec.id if sec else None,
            text=p.text,
            page=p.page,
            section_name=p.section_name,
            chunk_index=p.chunk_index,
            token_count=p.token_count,
        )
        db.session.add(row)
        chunk_rows.append(row)
    db.session.commit()

    paper.progress = 55
    paper.status_message = "Embedding"
    db.session.commit()

    texts = [c.text for c in chunk_rows]
    vectors = encode_texts(texts) if texts else None
    store = get_vector_store()
    if vectors is not None and len(chunk_rows):
        store.chunks.add_batch([c.id for c in chunk_rows], vectors)
    paper_vec = encode_texts([(paper.title or "") + "\n" + (paper.abstract or "")])
    store.papers.add(paper.id, paper_vec[0])
    store.persist()

    paper.progress = 75
    paper.status_message = "Updating keyword and BM25 indexes"
    db.session.commit()
    get_bm25().add_many([(c.id, c.text) for c in chunk_rows])
    blob = (paper.abstract or "") + "\n" + (parsed.full_text or "")[:8000]
    store_keywords(paper, blob)

    paper.progress = 90
    paper.status_message = "Fetching citation counts"
    db.session.commit()
    if not current_app.config.get("TESTING"):
        try:
            meta = lookup_citations(arxiv_id=paper.arxiv_id, title=paper.title)
            paper.citation_count = meta.get("citation_count") or 0
            if meta.get("venue") and not paper.venue:
                paper.venue = meta["venue"]
            if meta.get("doi") and not paper.doi:
                paper.doi = meta["doi"]
        except Exception:
            logger.exception("citation lookup failed")

    paper.status = "ready"
    paper.progress = 100
    paper.status_message = "Ready"
    db.session.commit()


def delete_paper(paper_id: int) -> bool:
    paper = Paper.query.get(paper_id)
    if not paper:
        return False
    chunk_ids = [c.id for c in paper.chunks.all()]
    store = get_vector_store()
    store.chunks.delete(chunk_ids)
    store.papers.delete([paper_id])
    store.persist()
    get_bm25().delete(chunk_ids)
    if paper.file_path:
        p = Path(paper.file_path)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                logger.warning("Could not delete file %s", p)
    db.session.delete(paper)
    db.session.commit()
    return True


def import_from_arxiv(arxiv_id: str, extra: dict | None = None) -> Paper:
    extra = extra or {}
    arxiv_id = arxiv_id.strip().replace("arxiv:", "")
    existing = Paper.query.filter_by(arxiv_id=arxiv_id).first()
    if existing:
        return existing
    dest = Path(current_app.config["DATA_DIR"]) / "uploads"
    path, info = download_pdf(arxiv_id, dest)
    file_hash = sha256_file(path)
    dup = Paper.query.filter_by(file_hash=file_hash).first()
    if dup:
        return dup
    paper = create_paper_record(
        title=extra.get("title") or info["title"],
        authors=extra.get("authors") or info.get("authors") or "",
        abstract=extra.get("abstract") or info.get("abstract") or "",
        year=extra.get("year") or info.get("year"),
        arxiv_id=info["arxiv_id"],
        file_hash=file_hash,
        file_path=str(path),
        source="arxiv",
        status="queued",
        status_message="Queued",
        progress=0,
    )
    schedule_ingest(current_app._get_current_object(), paper.id)
    return paper
