"""
Builds small synthetic PDFs for the tests: a PDD-shaped document with
sections and a table, a page with no text layer (like a scan), and a page of
broken-font gibberish. Real tricky PDFs from the registry get added in M2.

Run:  python tests/make_fixtures.py
"""

from pathlib import Path

import pymupdf as fitz

OUT = Path(__file__).parent / "fixtures"

SECTIONS = [
    ("SECTION A. Description of project activity", ""),
    ("A.1. Purpose and general description of project activity",
     "The project installs 30 wind turbines of 1.6 MW each near the coast. The electricity is "
     "delivered to the regional grid and displaces power from coal-fired plants. " * 6),
    ("A.2. Location of project activity",
     "The wind farm is located on Houhai peninsula, about 20 km from the city centre. " * 5),
    ("SECTION B. Application of selected approved baseline and monitoring methodology", ""),
    ("B.1. Reference of methodology",
     "The project applies the approved consolidated methodology ACM0002 version 12, "
     "Consolidated baseline methodology for grid-connected electricity generation from renewable sources. " * 4),
    ("B.6.1. Explanation of methodological choices",
     "The combined margin emission factor is calculated as a weighted average of the operating margin "
     "and build margin, with weights of 0.75 and 0.25 for wind projects. " * 5),
]
TABLE = [["Year", "Estimated reductions (tCO2e)"], ["2012", "61,240"], ["2013", "61,240"], ["2014", "61,240"],
         ["Total", "183,720"]]


def pdd(path: Path) -> None:
    doc = fitz.open()
    # Two sections per page, so one section (B.1) starts on a page the previous one didn't.
    for i, (heading, body) in enumerate(SECTIONS):
        if i % 2 == 0:
            page, y = doc.new_page(), 60
        page.insert_text((50, y), heading, fontsize=13, fontname="helv")
        if body:
            assert page.insert_textbox(fitz.Rect(50, y + 14, 545, y + 330), body, fontsize=10, fontname="helv") >= 0
        y += 360
    # A table on its own page, drawn with lines so pdfplumber can see it.
    page = doc.new_page()
    page.insert_text((50, 60), "B.6.4. Summary of the ex ante estimation of emission reductions", fontsize=13)
    x0, y0, w, h = 50, 90, 250, 22
    for r, row in enumerate(TABLE):
        for c, cell in enumerate(row):
            rect = fitz.Rect(x0 + c * w, y0 + r * h, x0 + (c + 1) * w, y0 + (r + 1) * h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.8)
            page.insert_text((rect.x0 + 5, rect.y0 + 15), cell, fontsize=10)
    doc.save(path)


def scanned(path: Path) -> None:
    """A page that is only an image: no text layer at all."""
    src = fitz.open(); p = src.new_page(); p.insert_text((50, 100), "Monitoring period 2019", fontsize=20)
    pix = p.get_pixmap(dpi=50)
    doc = fitz.open(); page = doc.new_page()
    page.insert_image(page.rect, pixmap=pix)
    doc.new_page().insert_text((50, 80), "C.1. Monitoring results", fontsize=13)
    doc.save(path)


def garbled(path: Path) -> None:
    doc = fitz.open(); page = doc.new_page()
    junk = "(cid:12)(cid:45)(cid:3) �� � (cid:88)(cid:99) " * 20
    page.insert_textbox(fitz.Rect(50, 50, 545, 400), junk, fontsize=10)
    doc.new_page()  # and a blank page
    doc.save(path)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    pdd(OUT / "pdd_sections_table.pdf"); scanned(OUT / "scanned_page.pdf"); garbled(OUT / "garbled_and_blank.pdf")
    print("fixtures written to", OUT)
