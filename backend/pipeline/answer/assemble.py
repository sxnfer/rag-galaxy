"""
Context assembly: choose what the model reads, and label it so it can cite.

  - drop near-duplicates (overlapping chunks repeat text),
  - stop at a word budget so the prompt stays small and cheap,
  - label each passage [S1], [S2]... with its breadcrumb and pages.

Cards made from a table (they carry "meta") are compared by what they are
about, not by their words: every card is written from the same template, so
two different cars share most of their words without being duplicates.
Their "page" is a row of the table.
"""

from dataclasses import dataclass


@dataclass
class Source:
    label: str          # "S1"
    chunk_id: int
    breadcrumb: str
    pages: str
    text: str
    score: float


def assemble(hits: list[dict], budget_words: int = 1500) -> tuple[list[Source], list[dict]]:
    """Returns the sources kept, and the hits dropped with the reason (for the trace)."""
    kept, dropped, used, seen = [], [], 0, []
    for h in hits:
        meta = h.get("meta")
        words = {(meta["item"], meta["facet"])} if meta else set(h["text"].lower().split())
        if any(len(words & s) / max(1, len(words)) > 0.8 for s in seen):
            dropped.append({"chunk_id": h["chunk_id"], "reason": "duplicate"})
            continue
        n = len(h["text"].split())
        if kept and used + n > budget_words:
            dropped.append({"chunk_id": h["chunk_id"], "reason": "over budget"})
            continue
        seen.append(words)
        used += n
        if meta:
            pages = f"row {h['page_start']}"
        else:
            pages = f"p. {h['page_start']}" if h["page_start"] == h["page_end"] else f"pp. {h['page_start']}-{h['page_end']}"
        kept.append(Source(f"S{len(kept) + 1}", h["chunk_id"], h["breadcrumb"], pages, h["text"], h["score"]))
    return kept, dropped


def render(sources: list[Source]) -> str:
    return "\n\n".join(f"[{s.label}] {s.breadcrumb} ({s.pages})\n{s.text}" for s in sources)
