"""Unified discovery across arXiv, OpenAlex, and Semantic Scholar."""

from __future__ import annotations

import logging
import time

import requests

from app.services.arxiv_client import search_arxiv
from app.services.openalex_client import search_openalex

logger = logging.getLogger(__name__)
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


def discover(query: str, sources: list[str] | None = None, max_per_source: int = 15) -> dict:
    sources = sources or ["arxiv", "openalex", "semantic_scholar"]
    max_per_source = min(max(max_per_source, 1), 50)
    results: dict[str, list] = {}
    errors: dict[str, str] = {}

    if "arxiv" in sources:
        try:
            results["arxiv"] = search_arxiv(query, max_results=max_per_source)
        except Exception as exc:  # noqa: BLE001
            errors["arxiv"] = str(exc)

    if "openalex" in sources:
        try:
            results["openalex"] = search_openalex(query, max_results=max_per_source)
        except Exception as exc:  # noqa: BLE001
            errors["openalex"] = str(exc)

    if "semantic_scholar" in sources:
        try:
            results["semantic_scholar"] = search_semantic_scholar(query, max_per_source)
        except Exception as exc:  # noqa: BLE001
            errors["semantic_scholar"] = str(exc)

    merged = []
    seen_titles: set[str] = set()
    for src, items in results.items():
        for item in items:
            key = (item.get("title") or "").lower()[:80]
            if key and key in seen_titles:
                continue
            if key:
                seen_titles.add(key)
            item = dict(item)
            item.setdefault("source", src)
            merged.append(item)

    return {
        "query": query,
        "by_source": results,
        "merged": merged,
        "total": len(merged),
        "errors": errors,
    }


def search_semantic_scholar(query: str, limit: int = 15) -> list[dict]:
    delay = 1.0
    for attempt in range(4):
        try:
            resp = requests.get(
                S2_SEARCH,
                params={
                    "query": query,
                    "limit": min(limit, 50),
                    "fields": "title,authors,abstract,year,externalIds,citationCount,openAccessPdf,venue",
                },
                timeout=15,
            )
            if resp.status_code == 429:
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            data = resp.json()
            out = []
            for p in data.get("data") or []:
                ext = p.get("externalIds") or {}
                oa = p.get("openAccessPdf") or {}
                out.append(
                    {
                        "source": "semantic_scholar",
                        "paper_id": p.get("paperId"),
                        "title": p.get("title"),
                        "authors": "; ".join(a.get("name", "") for a in (p.get("authors") or [])),
                        "abstract": p.get("abstract") or "",
                        "year": p.get("year"),
                        "arxiv_id": ext.get("ArXiv"),
                        "doi": ext.get("DOI"),
                        "pdf_url": oa.get("url"),
                        "citation_count": p.get("citationCount") or 0,
                        "venue": p.get("venue"),
                    }
                )
            return out
        except requests.RequestException:
            time.sleep(delay)
            delay *= 2
    return []
