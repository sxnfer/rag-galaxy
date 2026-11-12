"""PDF parsing on the three synthetic tricky PDFs."""

from pipeline.parse.pdf import parse_pdf
from conftest import FIXTURES


def test_keeps_pages_headings_and_tables():
    pages = parse_pdf(str(FIXTURES / "pdd_sections_table.pdf"))
    assert [p.page_no for p in pages] == [1, 2, 3, 4]
    headings = [h for p in pages for h in p.headings]
    assert "B.1. Reference of methodology" in headings
    table = pages[3].tables_md[0]
    assert "183,720" in table and table.startswith("| Year |")


def test_flags_a_page_with_no_text_layer():
    pages = parse_pdf(str(FIXTURES / "scanned_page.pdf"))
    assert pages[0].is_scanned and not pages[1].is_scanned


def test_blank_page_is_not_called_scanned():
    pages = parse_pdf(str(FIXTURES / "garbled_and_blank.pdf"))
    assert pages[1].text.strip() == "" and not pages[1].is_scanned
