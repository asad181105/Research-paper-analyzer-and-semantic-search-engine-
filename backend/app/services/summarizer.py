"""LLM structured summaries with extractive (sumy/TextRank) fallback."""

from __future__ import annotations

import json
import logging

from app.models import Paper, Section
from app.services import llm
from app.utils.json_util import parse_json_loose

logger = logging.getLogger(__name__)

SUMMARY_KEYS = (
    "tldr",
    "problem",
    "method",
    "dataset",
    "key_results",
    "limitations",
    "future_work",
)

SYSTEM = (
    "You are a research-paper analyst. Return ONLY valid JSON with keys: "
    "tldr, problem, method, dataset, key_results, limitations, future_work. "
    "tldr must be 1-2 sentences. Be faithful to the provided text; never invent numbers."
)


def summarize_paper(paper: Paper, regenerate: bool = False) -> tuple[dict, str]:
    """Return (summary_dict, mode) where mode is 'llm' or 'extractive'."""
    if paper.summary_json and not regenerate:
        try:
            return json.loads(paper.summary_json), "cached"
        except json.JSONDecodeError:
            pass

    pack = _context_pack(paper)
    if llm.llm_configured():
        try:
            summary = _llm_summarize(pack)
            paper.summary_json = json.dumps(summary)
            return summary, "llm"
        except Exception:
            logger.exception("LLM summarization failed; using extractive fallback")
    summary = extractive_summary(pack)
    paper.summary_json = json.dumps(summary)
    return summary, "extractive"


def _section_text(paper: Paper, name: str, limit: int = 4000) -> str:
    sec = paper.sections.filter_by(name=name).first()
    if not sec:
        return ""
    return (sec.text or "")[:limit]


def _context_pack(paper: Paper) -> dict[str, str]:
    return {
        "title": paper.title or "",
        "authors": paper.authors or "",
        "abstract": (paper.abstract or "")[:4000],
        "introduction": _section_text(paper, "introduction", 5000),
        "methodology": _section_text(paper, "methodology", 4000),
        "results": _section_text(paper, "results", 4000),
        "conclusion": _section_text(paper, "conclusion", 3000),
    }


def _llm_summarize(pack: dict[str, str]) -> dict:
    total = sum(len(v) for v in pack.values())
    if total < 24000:
        user = json.dumps(pack)
        raw = llm.complete(SYSTEM, "Summarize this paper:\n" + user)
        return _validate(parse_json_loose(raw))
    # map-reduce
    parts = []
    for key in ("abstract", "introduction", "methodology", "results", "conclusion"):
        if not pack.get(key):
            continue
        raw = llm.complete(
            "Summarize this section in 5 bullet points. Return plain text.",
            f"Section {key}:\n{pack[key][:6000]}",
            max_tokens=400,
        )
        parts.append(f"## {key}\n{raw}")
    raw = llm.complete(SYSTEM, "Combine these section notes into the JSON schema:\n" + "\n".join(parts))
    return _validate(parse_json_loose(raw))


def _validate(obj: object) -> dict:
    if not isinstance(obj, dict):
        obj = {"tldr": str(obj)}
    out = {}
    for k in SUMMARY_KEYS:
        val = obj.get(k, "")
        if isinstance(val, list):
            val = "; ".join(str(x) for x in val)
        out[k] = str(val or "").strip()
    if not out["tldr"]:
        out["tldr"] = "Summary unavailable."
    return out


def extractive_summary(pack: dict[str, str]) -> dict:
    text = "\n\n".join(
        pack.get(k, "")
        for k in ("abstract", "introduction", "methodology", "results", "conclusion")
        if pack.get(k)
    )
    sentences = _textrank_sentences(text, n=8)
    tldr = " ".join(sentences[:2]) if sentences else (pack.get("abstract") or "")[:400]
    return {
        "tldr": tldr or "No extractable summary.",
        "problem": _pick(sentences, pack.get("introduction", ""), "problem"),
        "method": _pick(sentences, pack.get("methodology", ""), "method"),
        "dataset": _pick(sentences, text, "dataset"),
        "key_results": _pick(sentences, pack.get("results", ""), "result"),
        "limitations": _pick(sentences, text, "limitation"),
        "future_work": _pick(sentences, pack.get("conclusion", ""), "future"),
    }


def _textrank_sentences(text: str, n: int = 8) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.summarizers.text_rank import TextRankSummarizer

        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = TextRankSummarizer()
        sents = [str(s) for s in summarizer(parser.document, n)]
        if sents:
            return sents
    except Exception:
        logger.info("sumy unavailable or failed; using lead sentences")
    parts = [s.strip() for s in text.replace("\n", " ").split(". ") if len(s.strip()) > 40]
    return parts[:n]


def _pick(sentences: list[str], fallback: str, keyword: str) -> str:
    keyed = [s for s in sentences if keyword.lower() in s.lower()]
    if keyed:
        return keyed[0]
    if fallback:
        parts = [s.strip() for s in fallback.replace("\n", " ").split(". ") if len(s.strip()) > 40]
        return (parts[0] if parts else fallback[:400])
    return sentences[0] if sentences else ""
