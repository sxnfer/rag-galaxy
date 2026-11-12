"""
Chunkers: cut parsed pages into passages small enough to be about one thing.

A chunk carries its own address (breadcrumb + pages), so an answer can cite
"Project X > PDD > B.6.1 Explanation of methodological choices, p. 23".
"""

import re
from dataclasses import dataclass

DOC_LABELS = {"pdd": "PDD", "validation_report": "Validation report",
              "monitoring_report": "Monitoring report", "other": "Document"}

# Pages flagged with any of these never become chunks.
SKIP_FLAGS = {"empty", "scanned", "garbled"}


@dataclass
class Page:
    page_no: int
    text: str
    headings: list[str]
    tables_md: list[str]
    flags: list[str]


@dataclass
class Chunk:
    text: str
    page_start: int
    page_end: int
    breadcrumb: str


def doc_prefix(project: str, doc_type: str) -> str:
    return f"{project} > {DOC_LABELS.get(doc_type, doc_type)}"


def usable(pages: list[Page]) -> list[Page]:
    return [p for p in pages if not (set(p.flags) & SKIP_FLAGS)]


def fixed_size_chunks(pages: list[Page], prefix: str, size: int = 300, overlap: int = 50) -> list[Chunk]:
    """
    The baseline: a window of `size` words that slides along the whole document,
    stepping `size - overlap` words each time. It ignores headings and tables,
    so it often cuts a section or a table in half. That's the point: it's the
    yardstick the structure-aware chunker has to beat.
    """
    words: list[tuple[str, int]] = [(w, p.page_no) for p in usable(pages) for w in p.text.split()]
    chunks = []
    for window in _windows(words, size, overlap):
        first, last = window[0][1], window[-1][1]
        pages_label = f"p. {first}" if first == last else f"pp. {first}-{last}"
        chunks.append(Chunk(" ".join(w for w, _ in window), first, last, f"{prefix} > {pages_label}"))
    return chunks


def _windows(words: list[tuple[str, int]], size: int, overlap: int):
    """Slide a window of `size` words along the list, stepping `size - overlap` words each time."""
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        yield words[start:start + size]
        if start + size >= len(words):
            break


# ---------------------------------------------------------------------------
# San wrote this (M3 core function #1).
#
# Input:  the usable pages of ONE document (use usable(pages)), the breadcrumb
#         prefix ("Project 5270 ... > PDD"), a target size in words, an overlap.
# Output: chunks that follow the document's structure:
#   - start a new chunk at each section heading (Page.headings lists the
#     headings found on that page, in order);
#   - keep each table whole (Page.tables_md), even if it's bigger than `size`;
#   - split a long section into pieces of about `size` words, overlapping by
#     `overlap` words;
#   - breadcrumb = prefix + " > " + the section heading, and set page_start /
#     page_end correctly when a section crosses pages.
# Tests that describe "done": tests/test_chunkers.py.
# ---------------------------------------------------------------------------
def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _table_cells(md: str) -> set[str]:
    cells = set()
    for row in md.splitlines():
        if row.startswith("|") and not row.startswith("|---"):
            cells.update(c.strip() for c in row.strip("|").split("|") if c.strip())
    return cells


def structure_aware_chunks(pages: list[Page], prefix: str, size: int = 300, overlap: int = 50) -> list[Chunk]:
    """
    1. Walk the lines of every usable page. A line that matches one of the page's
       headings closes the current section and opens a new one.
    2. Each table becomes ONE chunk, whatever its size, placed where its first cell
       appears. Its cells are dropped from the prose so the numbers aren't stored twice.
    3. Each section's prose is cut into overlapping windows of about `size` words.
    """
    chunks: list[Chunk] = []
    heading = "Front matter"                 # text before the first heading (cover page, title)
    words: list[tuple[str, int]] = []        # the current section's prose, word by word with its page

    def flush(keep_lone_heading: bool = False) -> None:
        # A section that is only its heading (e.g. "SECTION B. ..." right before "B.1.")
        # is carried into the next section instead of becoming a tiny useless chunk.
        if keep_lone_heading and words and len(words) <= len(heading.split()):
            return
        for window in _windows(words, size, overlap):
            first, last = window[0][1], window[-1][1]
            chunks.append(Chunk(" ".join(w for w, _ in window), first, last,
                                f"{prefix} > {heading}"))
        words.clear()

    for page in usable(pages):
        pending_headings = [_norm(h) for h in page.headings]
        tables = [(md, _table_cells(md)) for md in page.tables_md]
        all_cells = set().union(*(c for _, c in tables)) if tables else set()
        placed = [False] * len(tables)

        for raw in page.text.splitlines():
            line = _norm(raw)
            if not line:
                continue
            if pending_headings and line == pending_headings[0]:
                flush(keep_lone_heading=True)
                heading = pending_headings.pop(0)
                words.extend((w, page.page_no) for w in line.split())
                continue
            hit = next((i for i, (_, cells) in enumerate(tables) if not placed[i] and line in cells), None)
            if hit is not None:
                if len(words) <= len(heading.split()):
                    words.clear()   # only the heading so far; the table chunk carries it
                flush()             # the prose before the table becomes its own chunk(s)
                chunks.append(Chunk(f"{heading}\n{tables[hit][0]}", page.page_no, page.page_no,
                                    f"{prefix} > {heading} > table"))
                placed[hit] = True
            if line in all_cells:
                continue
            words.extend((w, page.page_no) for w in line.split())

        for i, (md, _) in enumerate(tables):  # a table whose cells we never spotted in the text
            if not placed[i]:
                chunks.append(Chunk(f"{heading}\n{md}", page.page_no, page.page_no, f"{prefix} > {heading} > table"))
    flush()
    return chunks


CHUNKERS = {"fixed": fixed_size_chunks, "structure": structure_aware_chunks}
