"""Queue many paper imports with simple rate limiting (in-process)."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, current_app

from app.extensions import db
from app.models import Paper
from app.services.ingest import import_from_arxiv, schedule_ingest, sha256_file
from app.services.openalex_client import get_work

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_active = 0
MAX_CONCURRENT = 2


def import_from_pdf_url(
    pdf_url: str,
    meta: dict | None = None,
    source: str = "url",
) -> Paper:
    meta = meta or {}
    dest = Path(current_app.config["DATA_DIR"]) / "uploads"
    dest.mkdir(parents=True, exist_ok=True)
    name = Path(urlparse(pdf_url).path).name or "paper.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    path = dest / name
    i = 1
    while path.exists():
        path = dest / f"{path.stem}_{i}.pdf"
        i += 1
    resp = requests.get(pdf_url, timeout=120, stream=True)
    resp.raise_for_status()
    with path.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    if path.stat().st_size < 64:
        path.unlink(missing_ok=True)
        raise ValueError("Downloaded file is too small")
    with path.open("rb") as f:
        if f.read(5) != b"%PDF-":
            path.unlink(missing_ok=True)
            raise ValueError("Downloaded file is not a valid PDF")
    file_hash = sha256_file(path)
    dup = Paper.query.filter_by(file_hash=file_hash).first()
    if dup:
        path.unlink(missing_ok=True)
        return dup
    doi = meta.get("doi")
    if doi:
        existing = Paper.query.filter_by(doi=doi).first()
        if existing:
            path.unlink(missing_ok=True)
            return existing
    from app.services.ingest import create_paper_record

    paper = create_paper_record(
        title=meta.get("title") or path.stem,
        authors=meta.get("authors") or "",
        abstract=meta.get("abstract") or "",
        year=meta.get("year"),
        arxiv_id=meta.get("arxiv_id"),
        doi=doi,
        venue=meta.get("venue"),
        citation_count=meta.get("citation_count") or 0,
        file_hash=file_hash,
        file_path=str(path),
        source=source,
        status="queued",
        status_message="Queued",
        progress=0,
    )
    schedule_ingest(current_app._get_current_object(), paper.id)
    return paper


def import_item(item: dict) -> dict:
    """Import one discovery result. Returns {status, paper?, message?}."""
    if item.get("arxiv_id"):
        try:
            paper = import_from_arxiv(str(item["arxiv_id"]), extra=item)
            return {"status": "queued", "paper": paper.to_dict()}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "message": str(exc), "item": item}

    if item.get("openalex_id"):
        work = get_work(str(item["openalex_id"]))
        if not work:
            return {"status": "error", "message": "OpenAlex work not found", "item": item}
        item = {**work, **item}

    pdf_url = item.get("pdf_url")
    if not pdf_url:
        return {"status": "skipped", "message": "No open-access PDF URL", "item": item}

    try:
        paper = import_from_pdf_url(pdf_url, meta=item, source=item.get("source", "url"))
        return {"status": "queued", "paper": paper.to_dict()}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc), "item": item}


def run_bulk_import(app: Flask, items: list[dict], delay_sec: float = 1.5) -> None:
    def worker():
        global _active
        with app.app_context():
            for raw in items:
                with _lock:
                    while _active >= MAX_CONCURRENT:
                        time.sleep(0.5)
                    _active += 1
                try:
                    import_item(raw)
                    db.session.remove()
                except Exception:
                    logger.exception("bulk import item failed")
                finally:
                    with _lock:
                        _active = max(0, _active - 1)
                time.sleep(delay_sec)

    threading.Thread(target=worker, daemon=True).start()


def queue_bulk_import(items: list[dict], delay_sec: float = 1.5) -> int:
    run_bulk_import(current_app._get_current_object(), items, delay_sec=delay_sec)
    return len(items)
