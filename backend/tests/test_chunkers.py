from pipeline.chunk.chunkers import Page, fixed_size_chunks, structure_aware_chunks
from pipeline.parse.pdf import parse_pdf
from conftest import FIXTURES


def pages():
    return [Page(p.page_no, p.text, p.headings, p.tables_md, []) for p in
            parse_pdf(str(FIXTURES / "pdd_sections_table.pdf"))]


def test_fixed_size_windows_overlap_and_cover_everything():
    ps = pages()
    chunks = fixed_size_chunks(ps, "P > PDD", size=100, overlap=20)
    words = sum(len(p.text.split()) for p in ps)
    assert all(len(c.text.split()) <= 100 for c in chunks)
    assert chunks[0].text.split()[-20:] == chunks[1].text.split()[:20]   # the overlap
    assert sum(len(c.text.split()) for c in chunks) >= words             # nothing lost
    assert chunks[-1].page_end == 4


def test_flagged_pages_are_skipped():
    ps = pages(); ps[0].flags = ["garbled"]
    assert all(c.page_start > 1 for c in fixed_size_chunks(ps, "P > PDD", 100, 20))


# --- San's structure-aware chunker ---

def test_structure_starts_chunks_at_headings():
    chunks = structure_aware_chunks(pages(), "P > PDD", 300, 50)
    assert any(c.breadcrumb == "P > PDD > B.1. Reference of methodology" for c in chunks)
    assert all(c.breadcrumb.startswith("P > PDD > ") for c in chunks)


def test_structure_keeps_tables_whole():
    chunks = structure_aware_chunks(pages(), "P > PDD", 30, 5)  # tiny size: the table must still be one chunk
    table_chunks = [c for c in chunks if "| Year |" in c.text]
    assert len(table_chunks) == 1 and "183,720" in table_chunks[0].text


def test_structure_respects_size():
    chunks = structure_aware_chunks(pages(), "P > PDD", 60, 10)
    assert all(len(c.text.split()) <= 60 or "| Year |" in c.text for c in chunks)
