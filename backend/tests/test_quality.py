"""San's M2 function: the page quality checks."""

from pipeline.parse.pdf import parse_pdf
from pipeline.parse.quality import check_page
from conftest import FIXTURES


def test_good_page_has_no_flags():
    page = parse_pdf(str(FIXTURES / "pdd_sections_table.pdf"))[0]
    assert check_page(page) == []


def test_blank_page_is_empty():
    page = parse_pdf(str(FIXTURES / "garbled_and_blank.pdf"))[1]
    assert "empty" in check_page(page)


def test_broken_font_is_garbled():
    page = parse_pdf(str(FIXTURES / "garbled_and_blank.pdf"))[0]
    assert "garbled" in check_page(page)


def test_scanned_page_is_flagged():
    page = parse_pdf(str(FIXTURES / "scanned_page.pdf"))[0]
    assert "scanned" in check_page(page)
