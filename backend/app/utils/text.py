import re
from typing import Iterable

HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
MULTI_SPACE = re.compile(r"[ \t]+")
MULTI_NL = re.compile(r"\n{3,}")
HEADER_FOOTER_NUM = re.compile(r"^\s*\d+\s*$")


def count_tokens(text: str) -> int:
    """Whitespace token approximation (CPU-friendly, no extra tokenizer)."""
    if not text:
        return 0
    return len(text.split())


def clean_page_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = HYPHEN_BREAK.sub(r"\1\2", text)
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if HEADER_FOOTER_NUM.match(stripped):
            continue
        lines.append(line)
    text = "\n".join(lines)
    text = MULTI_SPACE.sub(" ", text)
    text = MULTI_NL.sub("\n\n", text)
    return text.strip()


def normalize_whitespace(text: str) -> str:
    return MULTI_SPACE.sub(" ", (text or "").replace("\n", " ")).strip()


def highlight_passage(text: str, query: str, window: int = 420) -> str:
    """Return a snippet with matching query terms wrapped in <mark>."""
    if not text:
        return ""
    terms = [t for t in re.findall(r"[A-Za-z0-9]+", query or "") if len(t) > 2]
    lower = text.lower()
    pos = 0
    for term in terms:
        idx = lower.find(term.lower())
        if idx >= 0:
            pos = idx
            break
    start = max(0, pos - window // 3)
    end = min(len(text), start + window)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    if not terms:
        return snippet
    pattern = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)
    return pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", snippet)


def unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out
