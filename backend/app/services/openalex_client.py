"""OpenAlex work search (250M+ works, open metadata + OA PDF links)."""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)
BASE = "https://api.openalex.org"


def search_openalex(query: str, max_results: int = 25, filter_open_access: bool = True) -> list[dict]:
    params = {
        "search": query,
        "per-page": min(max_results, 50),
        "mailto": "paper-engine@local.dev",
    }
    if filter_open_access:
        params["filter"] = "open_access.is_oa:true"
    data = _get(f"{BASE}/works", params)
    rows = data.get("results") or []
    out = []
    for w in rows:
        out.append(_work_to_item(w))
    return out


def get_work(openalex_id: str) -> dict | None:
    oid = openalex_id.strip().replace("https://openalex.org/", "")
    if not oid.upper().startswith("W"):
        oid = f"W{oid}"
    data = _get(f"{BASE}/works/{oid}")
    if not data:
        return None
    return _work_to_item(data)


def _work_to_item(w: dict) -> dict:
    loc = w.get("primary_location") or {}
    pdf = loc.get("pdf_url")
    oa = (w.get("open_access") or {}).get("oa_url")
    pdf_url = pdf or oa
    authors = "; ".join(
        (a.get("author") or {}).get("display_name", "")
        for a in (w.get("authorships") or [])[:20]
        if (a.get("author") or {}).get("display_name")
    )
    ids = w.get("ids") or {}
    return {
        "source": "openalex",
        "openalex_id": w.get("id", "").replace("https://openalex.org/", ""),
        "title": (w.get("title") or "").strip(),
        "authors": authors,
        "abstract": _reconstruct_abstract(w.get("abstract_inverted_index")),
        "year": w.get("publication_year"),
        "doi": ids.get("doi", "").replace("https://doi.org/", "") if ids.get("doi") else None,
        "pdf_url": pdf_url,
        "venue": (w.get("primary_location") or {}).get("source", {}).get("display_name"),
        "citation_count": w.get("cited_by_count") or 0,
    }


def _reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in inv.items():
        for p in positions:
            words.append((p, word))
    words.sort(key=lambda x: x[0])
    return " ".join(w for _, w in words)[:8000]


def _get(url: str, params: dict | None = None, retries: int = 3) -> dict:
    delay = 1.0
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 429:
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == retries - 1:
                logger.warning("OpenAlex request failed: %s", url)
                return {}
            time.sleep(delay)
            delay *= 2
    return {}
