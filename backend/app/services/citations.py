"""Semantic Scholar Graph API lookup with retry/backoff and in-memory cache."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from flask import current_app

logger = logging.getLogger(__name__)
_cache: dict[str, dict[str, Any]] = {}
S2_URL = "https://api.semanticscholar.org/graph/v1/paper"


def lookup_citations(arxiv_id: str | None = None, doi: str | None = None, title: str | None = None) -> dict[str, Any]:
    key = arxiv_id or doi or (title or "")[:120]
    if not key:
        return {"citation_count": 0, "venue": None, "doi": None}
    if key in _cache:
        return _cache[key]
    headers = {}
    api_key = current_app.config.get("SEMANTIC_SCHOLAR_API_KEY") or ""
    if api_key:
        headers["x-api-key"] = api_key

    urls = []
    if arxiv_id:
        urls.append(f"{S2_URL}/ARXIV:{arxiv_id}")
    if doi:
        urls.append(f"{S2_URL}/DOI:{doi}")
    if title and not urls:
        urls.append(f"{S2_URL}/search")

    data: dict[str, Any] = {}
    for url in urls:
        try:
            if url.endswith("/search"):
                resp = _get(url, headers, params={"query": title, "limit": 1, "fields": "title,citationCount,venue,externalIds"})
                papers = (resp or {}).get("data") or []
                data = papers[0] if papers else {}
            else:
                data = _get(url, headers, params={"fields": "title,citationCount,venue,externalIds"}) or {}
            if data:
                break
        except Exception:
            logger.exception("Semantic Scholar lookup failed for %s", url)
            continue

    result = {
        "citation_count": int(data.get("citationCount") or 0),
        "venue": data.get("venue"),
        "doi": (data.get("externalIds") or {}).get("DOI") if isinstance(data.get("externalIds"), dict) else None,
        "s2_title": data.get("title"),
    }
    _cache[key] = result
    return result


def _get(url: str, headers: dict, params: dict | None = None, retries: int = 3) -> dict | None:
    delay = 1.0
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=8)
            if resp.status_code == 429:
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == retries - 1:
                logger.warning("S2 request failed after retries: %s", url)
                return {}
            time.sleep(delay)
            delay *= 2
    return {}
