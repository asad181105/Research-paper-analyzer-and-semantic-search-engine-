"""arXiv search and PDF download."""

from __future__ import annotations

import logging
from pathlib import Path

import arxiv

logger = logging.getLogger(__name__)


def search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    out = []
    for r in client.results(search):
        out.append(_result_to_dict(r))
    return out


def get_by_id(arxiv_id: str) -> dict | None:
    arxiv_id = arxiv_id.strip().replace("arxiv:", "").replace("https://arxiv.org/abs/", "")
    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    for r in client.results(search):
        return _result_to_dict(r)
    return None


def download_pdf(arxiv_id: str, dest_dir: Path) -> tuple[Path, dict]:
    info = get_by_id(arxiv_id)
    if not info:
        raise ValueError(f"arXiv id not found: {arxiv_id}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    client = arxiv.Client()
    search = arxiv.Search(id_list=[info["arxiv_id"]])
    paper = next(client.results(search))
    path = Path(paper.download_pdf(dirpath=str(dest_dir), filename=f"{info['arxiv_id']}.pdf"))
    return path, info


def _result_to_dict(r: arxiv.Result) -> dict:
    aid = r.get_short_id()
    authors = "; ".join(a.name for a in r.authors)
    year = r.published.year if r.published else None
    return {
        "arxiv_id": aid,
        "title": (r.title or "").replace("\n", " ").strip(),
        "authors": authors,
        "abstract": (r.summary or "").replace("\n", " ").strip(),
        "year": year,
        "pdf_url": r.pdf_url,
        "published": r.published.isoformat() if r.published else None,
        "primary_category": r.primary_category,
    }
