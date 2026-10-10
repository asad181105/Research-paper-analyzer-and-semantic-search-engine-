from pathlib import Path

import fitz

from app.services.chunker import chunk_paper, chunk_section
from app.services.pdf_parser import ParsedSection, parse_pdf


def _make_pdf(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), "Neural Rankers for Scientific Search", fontsize=20)
    page.insert_text((72, 90), "Jane Doe, John Smith", fontsize=11)
    page.insert_text((72, 130), "Abstract", fontsize=14)
    page.insert_text(
        (72, 150),
        "We propose a neural ranking model for scientific paper retrieval using dense embeddings.",
        fontsize=11,
    )
    page.insert_text((72, 200), "1 Introduction", fontsize=14)
    page.insert_text(
        (72, 220),
        "Information retrieval in scholarly corpora is challenging because of vocabulary mismatch. "
        "This paper studies dense retrieval for research papers.",
        fontsize=11,
    )
    page.insert_text((72, 320), "2 Methodology", fontsize=14)
    page.insert_text(
        (72, 340),
        "We encode title and abstract with a transformer encoder and score query-document cosine similarity.",
        fontsize=11,
    )
    page.insert_text((72, 420), "3 Results", fontsize=14)
    page.insert_text(
        (72, 440),
        "On a test collection of twenty queries our hybrid ranker improves nDCG@10 over BM25.",
        fontsize=11,
    )
    page.insert_text((72, 520), "4 Conclusion", fontsize=14)
    page.insert_text(
        (72, 540),
        "Dense retrieval complements lexical matching for research paper search.",
        fontsize=11,
    )
    page2 = doc.new_page()
    page2.insert_text((72, 60), "References", fontsize=14)
    page2.insert_text((72, 90), "[1] Dummy Citation. 2020.", fontsize=11)
    doc.save(str(path))
    doc.close()
    return path


def test_parse_pdf_sections(tmp_path):
    pdf = _make_pdf(tmp_path / "sample.pdf")
    parsed = parse_pdf(str(pdf))
    assert "Neural Rankers" in parsed.title
    names = {s.name for s in parsed.sections}
    assert "abstract" in names or parsed.abstract
    assert "introduction" in names
    assert "methodology" in names
    assert parsed.full_text
    assert "References" not in parsed.full_text or "Dummy Citation" not in parsed.full_text


def test_chunker_overlap_and_pages():
    sec = ParsedSection(
        name="methodology",
        title_raw="2 Methodology",
        text=" ".join(f"token{i}" for i in range(500)),
        page_start=2,
        page_end=5,
        order=2,
    )
    chunks = chunk_section(sec, target_tokens=300, overlap=50)
    assert len(chunks) >= 2
    assert chunks[0].token_count <= 300
    assert chunks[0].page >= 2
    first_tail = chunks[0].text.split()[-50:]
    second_head = chunks[1].text.split()[:50]
    assert first_tail == second_head


def test_chunk_paper_skips_references(tmp_path):
    pdf = _make_pdf(tmp_path / "s.pdf")
    parsed = parse_pdf(str(pdf))
    chunks = chunk_paper(parsed, 80, 10)
    assert chunks
    assert all(c.section_name != "references" for c in chunks)
