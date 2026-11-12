"""
Quality checks: catch pages that would poison the index before they get there.

A garbled page (broken font encoding) still "has text", so without a check it
gets chunked, embedded and retrieved, and the answer quotes nonsense.
"""

import re

from .pdf import ParsedPage

# Thresholds (defend these in an interview; tune them on real PDDs):
EMPTY_CHARS = 20        # fewer letters than this = nothing to index (page numbers, a lone header)
SHORT_WORDS = 40        # under ~40 words a chunk is mostly noise
GARBLED_BAD_SHARE = 0.05  # more than 5% replacement/cid junk characters = broken font encoding
GARBLED_WORD_SHARE = 0.5  # fewer than half the tokens look like real words = unreadable

_WORD = re.compile(r"^[A-Za-z][a-z]*[.,;:)]?$|^[A-Z]{2,}[.,;:)]?$|^\(?\d[\d.,%]*[.,;:)]?$")


# ---------------------------------------------------------------------------
# San wrote this (M2 core function).
#
# Input:  one ParsedPage (text, headings, tables_md, is_scanned, image_coverage).
# Output: a list of flag strings for that page. Suggested flags:
#   "empty"    - no meaningful text (think: what counts as meaningful?)
#   "scanned"  - no text layer, mostly image (pdf.py already sets is_scanned)
#   "garbled"  - text that isn't readable language, e.g. lots of "�",
#                "(cid:12)" codes, or very few real words
#   "short"    - a little text but probably not worth a chunk
# Rules: pure function, no I/O. Decide your thresholds and be ready to
# defend them in an interview ("why 30%?").
# Tests that describe "done": tests/test_quality.py.
# ---------------------------------------------------------------------------
def check_page(page: ParsedPage) -> list[str]:
    flags: list[str] = []
    text = page.text or ""
    if page.is_scanned:
        flags.append("scanned")
    letters = sum(ch.isalpha() for ch in text)
    if letters < EMPTY_CHARS:
        if "scanned" not in flags:
            flags.append("empty")
        return flags

    bad = text.count("\ufffd") + 6 * len(re.findall(r"\(cid:\d+\)", text))
    tokens = text.split()
    wordlike = sum(bool(_WORD.match(t)) for t in tokens) / max(1, len(tokens))
    if bad / max(1, len(text)) > GARBLED_BAD_SHARE or wordlike < GARBLED_WORD_SHARE:
        flags.append("garbled")
    elif len(tokens) < SHORT_WORDS and not page.tables_md:
        flags.append("short")
    return flags


def report(pages: list[ParsedPage], flags: list[list[str]]) -> dict:
    """The per-document quality report stored in quality_reports."""
    def count(flag: str) -> int:
        return sum(flag in page_flags for page_flags in flags)

    return {
        "pages": len(pages),
        "pages_with_text": sum(1 for p in pages if p.text.strip()),
        "empty": count("empty"),
        "scanned": count("scanned"),
        "garbled": count("garbled"),
        "short": count("short"),
        "tables": sum(len(p.tables_md) for p in pages),
        "headings": sum(len(p.headings) for p in pages),
    }
