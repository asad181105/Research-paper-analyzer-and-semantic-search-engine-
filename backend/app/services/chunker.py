"""Section-aware chunking (~300 tokens, 50 overlap) preserving page numbers."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.pdf_parser import ParsedPaper, ParsedSection
from app.utils.text import count_tokens


@dataclass
class TextChunk:
    text: str
    section_name: str
    page: int
    chunk_index: int
    token_count: int
    section_order: int


def chunk_paper(
    parsed: ParsedPaper,
    target_tokens: int = 300,
    overlap: int = 50,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    idx = 0
    for sec in parsed.sections:
        if sec.name == "references":
            continue
        for piece in chunk_section(sec, target_tokens, overlap):
            piece.chunk_index = idx
            chunks.append(piece)
            idx += 1
    if not chunks and parsed.full_text:
        dummy = ParsedSection(
            name="other",
            title_raw="Body",
            text=parsed.full_text,
            page_start=1,
            page_end=max(len(parsed.pages), 1),
            order=0,
        )
        for piece in chunk_section(dummy, target_tokens, overlap):
            piece.chunk_index = idx
            chunks.append(piece)
            idx += 1
    return chunks


def chunk_section(
    section: ParsedSection,
    target_tokens: int = 300,
    overlap: int = 50,
) -> list[TextChunk]:
    words = (section.text or "").split()
    if not words:
        return []
    page_span = max(section.page_end - section.page_start, 0)
    chunks: list[TextChunk] = []
    start = 0
    local_i = 0
    n = len(words)
    step = max(target_tokens - overlap, 1)
    while start < n:
        end = min(start + target_tokens, n)
        piece_words = words[start:end]
        text = " ".join(piece_words)
        frac = start / max(n, 1)
        page = section.page_start + int(round(frac * page_span))
        chunks.append(
            TextChunk(
                text=text,
                section_name=section.name,
                page=max(page, 1),
                chunk_index=local_i,
                token_count=count_tokens(text),
                section_order=section.order,
            )
        )
        local_i += 1
        if end >= n:
            break
        start += step
    return chunks
