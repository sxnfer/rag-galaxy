"""
M3 runner: chunk every parsed document with one chunker + size, embed the
chunks, and store them with the model name and version on every row.

One (library, chunker, size) is a "run". Runs live side by side in the chunks
table so M4 can compare them on the same golden set.

A table library (the electric cars) skips the page step: its registered CSV goes
straight to the cards chunker, and each card's raw numbers are stored in
chunks.meta. Its run is always cards/0.
"""

import numpy as np
from psycopg.types.json import Jsonb

from app.embedder import load_embedder

from ..db import connect
from ..libraries import is_table, run_of
from .chunkers import CHUNKERS, Page, doc_prefix

INSERT = """insert into chunks (library, doc_sha256, chunker, chunk_size, ord, page_start, page_end,
                                breadcrumb, text, model, model_version, embedding, meta)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""


def store(conn, library: str, sha: str, chunker: str, size: int, chunks: list, embedder) -> None:
    """Embed one document's chunks and replace whatever this run stored for it before."""
    vectors = embedder.embed_passages([c.text for c in chunks])
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)  # length 1: cosine = dot product
    conn.execute("delete from chunks where doc_sha256=%s and chunker=%s and chunk_size=%s", (sha, chunker, size))
    for i, (c, v) in enumerate(zip(chunks, vectors, strict=True)):
        meta = getattr(c, "meta", None)  # only cards carry raw numbers
        conn.execute(INSERT, (library, sha, chunker, size, i, c.page_start, c.page_end, c.breadcrumb, c.text,
                              embedder.name, embedder.version, v.astype(np.float32), Jsonb(meta) if meta else None))
    conn.commit()


def run_table(library: str) -> dict:
    """The cards run for a table library: the newest registered CSV -> one card per car and facet."""
    from ..collect.table import latest, load
    from .cards import car_cards

    chunker, size = run_of(library, "cards", 0)
    embedder = load_embedder()
    with connect() as conn:
        sheet = latest(conn, library)
        if not sheet:
            raise SystemExit(f"No stat sheet registered for {library!r}: run `python -m pipeline register --library {library}`")
        sha, path = sheet
        rows = load(path)
        cards = car_cards(rows)
        # Cards made from an older version of the CSV would answer with old numbers, so they go.
        conn.execute("delete from chunks where library=%s and chunker=%s and doc_sha256 <> %s", (library, chunker, sha))
        store(conn, library, sha, chunker, size, cards, embedder)
    print(f"  {len(rows)} rows -> {len(cards)} cards")
    print(f"Stored {len(cards)} chunks for run {library}/{chunker}/{size} with {embedder.name}")
    return {"chunks": len(cards)}


def load_pages(conn, sha: str) -> list[Page]:
    rows = conn.execute(
        "select page_no, text, headings, tables_md, flags from pages where doc_sha256 = %s order by page_no",
        (sha,)).fetchall()
    return [Page(*r) for r in rows]


def run(library: str, chunker: str = "fixed", size: int = 300, overlap: int = 50) -> dict:
    if is_table(library):
        return run_table(library)
    chunk_fn = CHUNKERS[chunker]
    embedder = load_embedder()
    total = 0
    with connect() as conn:
        docs = conn.execute(
            """select distinct m.sha256, m.project_id, coalesce(m.project_title, m.project_id), m.doc_type
               from manifest m join pages p on p.doc_sha256 = m.sha256
               where m.library = %s order by 2, 4""", (library,)).fetchall()
        for sha, pid, title, dtype in docs:
            chunks = chunk_fn(load_pages(conn, sha), doc_prefix(title, dtype), size, overlap)
            if not chunks:
                print(f"  {pid} {dtype}: no usable text, skipped")
                continue
            store(conn, library, sha, chunker, size, chunks, embedder)
            total += len(chunks)
            print(f"  {pid} {dtype}: {len(chunks)} chunks")
    print(f"Stored {total} chunks for run {library}/{chunker}/{size} with {embedder.name}")
    return {"chunks": total}
