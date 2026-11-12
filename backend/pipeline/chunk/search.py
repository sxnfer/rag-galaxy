"""
Three ways to find the chunks closest to a question, from simplest to fastest:

  1. cosine_search  - NumPy, exact: compare the question with every chunk.
  2. sql_exact      - the same maths, done inside Postgres by pgvector.
  3. sql_hnsw       - approximate: an HNSW index walks a graph of neighbours
                      instead of checking everything. Much faster on big
                      collections, but it can miss a true neighbour. We
                      measure how often (recall of HNSW vs exact).
"""

import re
from dataclasses import dataclass

import numpy as np

from ..db import as_np, connect


@dataclass
class Hit:
    chunk_id: int
    score: float      # cosine similarity: 1 = same direction, 0 = unrelated


# ---------------------------------------------------------------------------
# San wrote this (M3 core function #2).
#
# Input:  query  - one vector, shape (384,), already length 1
#         matrix - every chunk's vector, shape (n_chunks, 384), each length 1
#         k      - how many to return
# Output: the positions (row numbers) of the k most similar rows and their
#         cosine scores, best first: list[tuple[int, float]].
# Hint: lesson 02 normalisation. Once every vector has length 1, cosine
# similarity is a dot product. No loops needed.
# Tests that describe "done": tests/test_search.py.
# ---------------------------------------------------------------------------
def cosine_search(query: np.ndarray, matrix: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
    if len(matrix) == 0:
        return []
    scores = matrix @ query                 # every vector has length 1, so dot product = cosine
    k = min(k, len(scores))
    top = np.argpartition(-scores, k - 1)[:k]   # the k best, unordered (fast on big matrices)
    top = top[np.argsort(-scores[top])]         # now best first
    return [(int(i), float(scores[i])) for i in top]


# A run is (library, chunker, chunk_size, model). Filtering on the library here,
# inside the search, is "metadata filtering" (lesson 02): the top k all come
# from the chosen library, instead of searching everything and throwing some away.
RUN_FILTER = "library = %s and chunker = %s and chunk_size = %s and model = %s"


def sql_exact(conn, query: np.ndarray, run: tuple[str, str, int, str], k: int = 5) -> list[Hit]:
    """Exact search inside Postgres. Index scans are switched off so every row is compared."""
    conn.execute("set local enable_indexscan = off")
    rows = conn.execute(
        f"""select id, 1 - (embedding <=> %s) as score from chunks
            where {RUN_FILTER} order by embedding <=> %s limit %s""",
        (query.astype(np.float32), *run, query.astype(np.float32), k)).fetchall()
    return [Hit(int(i), float(s)) for i, s in rows]


def hnsw_index_name(run: tuple[str, str, int, str]) -> str:
    library, chunker, size, _ = run
    name = f"chunks_hnsw_{library}_{chunker}_{int(size)}"
    if not re.fullmatch(r"[a-z0-9_]+", name):  # it goes into SQL as a name, so only plain characters
        raise ValueError(f"run {library}/{chunker} can't be used in an index name")
    return name


def _run_where(run: tuple[str, str, int, str]) -> str:
    """The run as literal SQL. Index definitions and planner matching need literals,
    so the values are checked first: they come from our own config, never a visitor."""
    library, chunker, size, model = run
    for v in (library, chunker, model):
        if "'" in v:
            raise ValueError(f"unexpected quote in run value {v!r}")
    return f"library = '{library}' and chunker = '{chunker}' and chunk_size = {int(size)} and model = '{model}'"


def build_hnsw(run: tuple[str, str, int, str], m: int = 16, ef_construction: int = 64) -> None:
    """One partial HNSW index per library + run, so filtering doesn't fight the index."""
    with connect() as conn:
        conn.execute(f"drop index if exists {hnsw_index_name(run)}")
        conn.execute(
            f"""create index {hnsw_index_name(run)} on chunks
                using hnsw (embedding vector_cosine_ops) with (m = {int(m)}, ef_construction = {int(ef_construction)})
                where {_run_where(run)}""")
        conn.commit()


def sql_hnsw(conn, query: np.ndarray, run: tuple[str, str, int, str], k: int = 5, ef_search: int = 40) -> list[Hit]:
    conn.execute(f"set local hnsw.ef_search = {int(ef_search)}")
    conn.execute("set local enable_seqscan = off")  # make sure the index is used
    rows = conn.execute(
        f"""select id, 1 - (embedding <=> %s) as score from chunks
            where {_run_where(run)}
            order by embedding <=> %s limit %s""",
        (query.astype(np.float32), query.astype(np.float32), k)).fetchall()
    return [Hit(int(i), float(s)) for i, s in rows]


def load_matrix(conn, run: tuple[str, str, int, str]) -> tuple[list[int], np.ndarray]:
    rows = conn.execute(f"select id, embedding from chunks where {RUN_FILTER} order by id", run).fetchall()
    return [r[0] for r in rows], np.array([as_np(r[1]) for r in rows])


def search(conn, query: np.ndarray, run: tuple[str, str, int, str], k: int = 5, method: str = "exact") -> list[Hit]:
    """What the app and the evaluation call. method: exact (Postgres), hnsw (the index) or numpy (cosine_search)."""
    if method == "hnsw":
        return sql_hnsw(conn, query, run, k)
    if method == "numpy":
        ids, matrix = load_matrix(conn, run)
        return [Hit(ids[i], s) for i, s in cosine_search(query, matrix, k)]
    return sql_exact(conn, query, run, k)


def hnsw_recall(run: tuple[str, str, int, str], queries: np.ndarray, k: int = 5, ef_search: int = 40) -> float:
    """Share of the exact top-k that HNSW also returns, averaged over the queries."""
    found = []
    with connect() as conn:
        for q in queries:
            exact = {h.chunk_id for h in sql_exact(conn, q, run, k)}
            approx = {h.chunk_id for h in sql_hnsw(conn, q, run, k, ef_search)}
            conn.rollback()  # clear the "set local" settings between queries
            found.append(len(exact & approx) / max(1, len(exact)))
    return float(np.mean(found)) if found else float("nan")
