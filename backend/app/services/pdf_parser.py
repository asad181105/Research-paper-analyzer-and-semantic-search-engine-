"""PDF -> structured sections using PyMuPDF font heuristics."""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

import fitz

from app.utils.text import clean_page_text, normalize_whitespace

logger = logging.getLogger(__name__)

CANONICAL = (
    "abstract",
    "introduction",
    "related_work",
    "methodology",
    "results",
    "discussion",
    "conclusion",
    "references",
    "other",
)

SECTION_ALIASES = {
    "abstract": "abstract",
    "introduction": "introduction",
    "intro": "introduction",
    "related work": "related_work",
    "related works": "related_work",
    "background": "related_work",
    "literature review": "related_work",
    "prior work": "related_work",
    "method": "methodology",
    "methods": "methodology",
    "methodology": "methodology",
    "approach": "methodology",
    "model": "methodology",
    "models": "methodology",
    "experimental setup": "methodology",
    "experiments": "results",
    "experiment": "results",
    "results": "results",
    "evaluation": "results",
    "findings": "results",
    "discussion": "discussion",
    "analysis": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "concluding remarks": "conclusion",
    "future work": "conclusion",
    "limitations": "discussion",
    "references": "references",
    "bibliography": "references",
    "acknowledgements": "other",
    "acknowledgments": "other",
    "appendix": "other",
}

HEADING_RE = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*)|(?:[IVXivx]+\.?))\s+[:.\-]?\s*(.+)$"
)
BARE_HEADING_RE = re.compile(r"^[A-Z][A-Za-z &/\-]{2,60}$")
AUTHOR_LINE_RE = re.compile(
    r"^[A-Z][a-zA-Z.\-]+(?:\s+[A-Z][a-zA-Z.\-]+){0,4}(?:,\s*[A-Z][a-zA-Z.\-]+)*$"
)


@dataclass
class SpanInfo:
    text: str
    size: float
    bold: bool
    page: int
    y0: float


@dataclass
class ParsedSection:
    name: str
    title_raw: str
    text: str
    page_start: int
    page_end: int
    order: int


@dataclass
class ParsedPaper:
    title: str
    authors: str
    abstract: str
    year: int | None
    pages: list[str]
    sections: list[ParsedSection] = field(default_factory=list)
    full_text: str = ""


def parse_pdf(path: str) -> ParsedPaper:
    try:
        doc = fitz.open(path)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Corrupt or unreadable PDF: {exc}") from exc

    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF has no pages")

    page_texts: list[str] = []
    all_spans: list[SpanInfo] = []
    body_sizes: list[float] = []

    try:
        for i, page in enumerate(doc):
            page_no = i + 1
            raw = page.get_text("text") or ""
            page_texts.append(clean_page_text(raw))
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = (span.get("text") or "").strip()
                        if not txt:
                            continue
                        size = float(span.get("size") or 0)
                        font = (span.get("font") or "").lower()
                        bold = "bold" in font or "black" in font or (span.get("flags", 0) & 2**4)
                        bbox = span.get("bbox") or [0, 0, 0, 0]
                        all_spans.append(
                            SpanInfo(text=txt, size=size, bold=bold, page=page_no, y0=bbox[1])
                        )
                        if size:
                            body_sizes.append(size)
    finally:
        doc.close()

    median_size = _median(body_sizes) if body_sizes else 10.0
    title = _detect_title(all_spans, page_texts)
    authors = _detect_authors(all_spans, title)
    year = _detect_year("\n".join(page_texts[:2]))
    sections = _split_sections(all_spans, page_texts, median_size, title)

    abstract = ""
    for sec in sections:
        if sec.name == "abstract":
            abstract = sec.text
            break
    if not abstract:
        abstract = _extract_abstract_fallback(page_texts[0] if page_texts else "")

    body_sections = []
    stopped = False
    for sec in sections:
        if sec.name == "references":
            body_sections.append(sec)
            stopped = True
            continue
        if stopped:
            continue
        body_sections.append(sec)

    full_text = "\n\n".join(s.text for s in body_sections if s.name != "references")
    return ParsedPaper(
        title=title or "Untitled",
        authors=authors,
        abstract=abstract,
        year=year,
        pages=page_texts,
        sections=body_sections,
        full_text=full_text,
    )


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def _detect_title(spans: list[SpanInfo], page_texts: list[str]) -> str:
    first = [s for s in spans if s.page == 1 and len(s.text) > 3]
    if not first:
        first_line = (page_texts[0].split("\n")[0] if page_texts else "").strip()
        return first_line[:300] or "Untitled"
    top = sorted(first, key=lambda s: (s.y0, -s.size))[:40]
    max_size = max(s.size for s in top)
    title_spans = [s for s in top if s.size >= max_size - 0.6 and s.y0 < 280]
    title = normalize_whitespace(" ".join(s.text for s in title_spans))
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) < 8:
        title = normalize_whitespace(page_texts[0].split("\n")[0]) if page_texts else title
    return title[:500] or "Untitled"


def _detect_authors(spans: list[SpanInfo], title: str) -> str:
    first = [s for s in spans if s.page == 1]
    collected: list[str] = []
    seen_title = False
    for s in sorted(first, key=lambda x: x.y0):
        t = s.text.strip()
        if title and t[:20] in title:
            seen_title = True
            continue
        if not seen_title:
            continue
        low = t.lower()
        if low.startswith("abstract") or low.startswith("index terms"):
            break
        if "@" in t or "university" in low or "institute" in low or "department" in low:
            continue
        if AUTHOR_LINE_RE.match(t) or ("," in t and t[0].isupper() and len(t) < 180):
            collected.append(t)
        if len(collected) >= 6:
            break
    return "; ".join(collected)[:1000]


def _detect_year(text: str) -> int | None:
    years = re.findall(r"\b(19|20)\d{2}\b", text[:4000])
    if not years:
        return None
    # re.findall with group returns only the 19|20 prefix; search full years instead
    full = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", text[:4000])]
    plausible = [y for y in full if 1980 <= y <= 2030]
    return plausible[0] if plausible else None


def _normalize_heading(raw: str) -> str | None:
    cleaned = re.sub(r"^\s*(?:\d+(?:\.\d+)*|[IVXivx]+\.?)\s*[:.\-]?\s*", "", raw)
    cleaned = cleaned.strip().lower()
    cleaned = re.sub(r"[^a-z ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned in SECTION_ALIASES:
        return SECTION_ALIASES[cleaned]
    for key, val in SECTION_ALIASES.items():
        if cleaned.startswith(key) or key in cleaned:
            return val
    return None


def _is_heading(span: SpanInfo, median_size: float) -> bool:
    text = span.text.strip()
    if len(text) < 3 or len(text) > 80:
        return False
    if text.endswith(".") and len(text.split()) > 8:
        return False
    large = span.size >= median_size + 1.2
    numbered = bool(HEADING_RE.match(text))
    bare = bool(BARE_HEADING_RE.match(text)) and (span.bold or large)
    if (large or span.bold or numbered) and (
        numbered or bare or _normalize_heading(text) is not None
    ):
        return True
    return False


def _split_sections(
    spans: list[SpanInfo],
    page_texts: list[str],
    median_size: float,
    title: str,
) -> list[ParsedSection]:
    headings: list[tuple[int, str, str, int]] = []  # order, name, raw, page
    # Flatten lines by concatenating nearby spans on same y
    lines: list[SpanInfo] = _merge_line_spans(spans)
    for idx, span in enumerate(lines):
        if span.page > 1 and span.size < median_size:
            # skip likely running headers
            if span.y0 < 50:
                continue
        if _is_heading(span, median_size):
            name = _normalize_heading(span.text)
            if name:
                headings.append((idx, name, span.text.strip(), span.page))

    if not any(h[1] == "abstract" for h in headings):
        headings.insert(0, (0, "abstract", "Abstract", 1))

    # Deduplicate consecutive same names
    compact: list[tuple[int, str, str, int]] = []
    for h in headings:
        if compact and compact[-1][1] == h[1]:
            continue
        compact.append(h)
    headings = compact

    # Build section text from full page text using heading strings as split points
    joined = ""
    page_offsets: list[tuple[int, int]] = []  # page, start offset
    for i, pt in enumerate(page_texts):
        page_offsets.append((i + 1, len(joined)))
        joined += pt + "\n\n"

    # Cut body at references
    ref_match = re.search(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?references\b", joined)
    body = joined if not ref_match else joined[: ref_match.start()]
    ref_text = joined[ref_match.start() :] if ref_match else ""

    split_points: list[tuple[int, str, str]] = []
    for _, name, raw, _page in headings:
        if name == "references":
            continue
        pat = re.compile(re.escape(raw), re.IGNORECASE)
        m = pat.search(body)
        if m:
            split_points.append((m.start(), name, raw))
    split_points.sort(key=lambda x: x[0])

    sections: list[ParsedSection] = []
    if not split_points:
        sections.append(
            ParsedSection("other", "Body", body.strip(), 1, max(len(page_texts), 1), 0)
        )
    else:
        for i, (start, name, raw) in enumerate(split_points):
            end = split_points[i + 1][0] if i + 1 < len(split_points) else len(body)
            chunk = body[start:end]
            # strip the heading line
            chunk = re.sub(r"^.*\n", "", chunk, count=1).strip()
            p_start = _page_for_offset(page_offsets, start)
            p_end = _page_for_offset(page_offsets, end - 1 if end else start)
            sections.append(
                ParsedSection(name, raw, chunk, p_start, p_end, i)
            )

    if ref_text:
        sections.append(
            ParsedSection(
                "references",
                "References",
                ref_text.strip()[:20000],
                _page_for_offset(page_offsets, ref_match.start() if ref_match else 0),
                len(page_texts),
                len(sections),
            )
        )

    if not any(s.name == "abstract" for s in sections) and page_texts:
        abs_text = _extract_abstract_fallback(page_texts[0])
        if abs_text:
            sections.insert(
                0, ParsedSection("abstract", "Abstract", abs_text, 1, 1, 0)
            )
            for i, s in enumerate(sections):
                s.order = i

    return sections


def _merge_line_spans(spans: list[SpanInfo]) -> list[SpanInfo]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (s.page, round(s.y0, 1), -s.size))
    merged: list[SpanInfo] = []
    buf: list[SpanInfo] = []

    def flush():
        if not buf:
            return
        text = " ".join(s.text for s in buf)
        size = max(s.size for s in buf)
        bold = any(s.bold for s in buf)
        merged.append(SpanInfo(text=text, size=size, bold=bold, page=buf[0].page, y0=buf[0].y0))
        buf.clear()

    for s in ordered:
        if not buf:
            buf.append(s)
            continue
        if s.page == buf[0].page and abs(s.y0 - buf[0].y0) < 2.5:
            buf.append(s)
        else:
            flush()
            buf.append(s)
    flush()
    return merged


def _page_for_offset(page_offsets: list[tuple[int, int]], offset: int) -> int:
    page = 1
    for p, start in page_offsets:
        if start <= offset:
            page = p
        else:
            break
    return page


def _extract_abstract_fallback(first_page: str) -> str:
    m = re.search(r"(?is)abstract\s*[:\-]?\s*(.+?)(?:\n\s*\n|introduction\b|1\s+introduction)", first_page)
    if m:
        return normalize_whitespace(m.group(1))[:4000]
    # first reasonably long paragraph
    paras = [p.strip() for p in first_page.split("\n\n") if len(p.strip()) > 80]
    return paras[1] if len(paras) > 1 else (paras[0] if paras else "")


def detect_repeated_headers(page_texts: list[str]) -> set[str]:
    counts: Counter[str] = Counter()
    for pt in page_texts:
        for line in pt.split("\n")[:3] + pt.split("\n")[-3:]:
            t = line.strip()
            if 8 < len(t) < 80:
                counts[t] += 1
    return {k for k, v in counts.items() if v >= max(2, len(page_texts) // 2)}
