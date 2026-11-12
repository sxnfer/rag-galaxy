"""
Read one PDF into pages.

  - Text per page with PyMuPDF (fast, keeps reading order well).
  - Headings: lines that look like section titles, e.g. "A.2. Location of project
    activity" or bold lines in a bigger font. PDDs use a fixed section template
    (A, B, C...), which is what makes structure-aware chunking possible in M3.
  - Tables with pdfplumber, turned into Markdown so they survive as text.
  - Scanned pages: almost no text layer but an image covering the page.
    We flag them; reading them would need OCR (a stretch goal).
"""

import re
import statistics
from dataclasses import dataclass, field

import pymupdf as fitz  # PyMuPDF
import pdfplumber

HEADING_RE = re.compile(r"^(SECTION\s+[A-Z]\.?|[A-H]\.\d+(\.\d+)*\.?|\d+(\.\d+)*\.?)\s+\S.{2,120}$")


@dataclass
class ParsedPage:
    page_no: int
    text: str
    headings: list[str] = field(default_factory=list)
    tables_md: list[str] = field(default_factory=list)
    is_scanned: bool = False
    image_coverage: float = 0.0   # share of the page covered by images, 0..1


def _headings(page: "fitz.Page") -> list[str]:
    lines = [line for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])]
    sizes = [s["size"] for line in lines for s in line["spans"] if s["text"].strip()]
    body = statistics.median(sizes) if sizes else 0
    found = []
    for line in lines:
        text = "".join(s["text"] for s in line["spans"]).strip()
        if not text or len(text) > 140:
            continue
        big = max(s["size"] for s in line["spans"]) >= body + 1.5
        bold = all(s["flags"] & 16 for s in line["spans"] if s["text"].strip())
        if HEADING_RE.match(text) or (big and len(text) < 90) or (bold and len(text) < 90 and text[0].isupper()):
            found.append(re.sub(r"\s+", " ", text))
    return found


def _table_md(rows: list[list[str | None]]) -> str:
    clean = [[(c or "").replace("\n", " ").strip() for c in r] for r in rows if any(c for c in r)]
    if not clean:
        return ""
    width = max(len(r) for r in clean)
    clean = [r + [""] * (width - len(r)) for r in clean]
    lines = ["| " + " | ".join(clean[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in clean[1:]]
    return "\n".join(lines)


def parse_pdf(path: str) -> list[ParsedPage]:
    pages: list[ParsedPage] = []
    with fitz.open(path) as doc, pdfplumber.open(path) as plumb:
        for i, page in enumerate(doc):
            text = page.get_text("text")
            area = page.rect.width * page.rect.height or 1
            img_area = sum((r.width * r.height) for img in page.get_images(full=True)
                           for r in page.get_image_rects(img[0]))
            coverage = min(1.0, img_area / area)
            scanned = len(text.strip()) < 25 and coverage > 0.5
            try:
                tables = [md for t in plumb.pages[i].extract_tables() if (md := _table_md(t))]
            except Exception:  # pdfplumber can choke on odd pages; the text still counts
                tables = []
            pages.append(ParsedPage(i + 1, text, _headings(page), tables, scanned, round(coverage, 3)))
    return pages
