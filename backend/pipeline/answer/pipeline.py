"""
The whole request path for one question, timed stage by stage. Returns the
trace the browser replays. Stage ids match the frontend.

A library with "rank" switched on (the electric cars) gets one extra stage between
search and assemble: search returns more candidates, and rank.py sorts them
by the stat the question asks for.
"""

import time
import uuid

import numpy as np
from psycopg.types.json import Jsonb

from ..db import connect
from ..chunk.search import search
from ..libraries import LIBRARIES
from .assemble import assemble
from .check import check
from .generate import generate
from .rank import CANDIDATES, rank


def _ms(t: float) -> int:
    return max(1, round((time.perf_counter() - t) * 1000))


def answer(question: str, embedder, run: tuple[str, str, int, str], k: int = 5) -> dict:
    """run = (library, chunker, chunk_size, model): which library to search, and how it was chunked."""
    stages = []
    ranked = bool(LIBRARIES.get(run[0], {}).get("rank"))
    wanted = max(k, CANDIDATES) if ranked else k  # a ranked library searches wide, then sorts
    t = time.perf_counter()
    q = embedder.embed_query(question)
    q = q / np.linalg.norm(q)
    stages.append({"id": "query", "label": "Turn it into numbers", "duration_ms": _ms(t),
                   "detail": f"{len(q)} numbers from {embedder.name}"})

    with connect() as conn:
        t = time.perf_counter()
        found = search(conn, q, run, k=wanted)
        conn.rollback()
        rows = conn.execute(
            """select c.id, c.breadcrumb, c.page_start, c.page_end, c.text, m.project_id, m.doc_type, c.meta
               from chunks c join manifest m on m.sha256 = c.doc_sha256 where c.id = any(%s)""",
            ([h.chunk_id for h in found],)).fetchall()
        by_id = {r[0]: r for r in rows}
        hits = [{"chunk_id": h.chunk_id, "score": round(h.score, 4), "breadcrumb": by_id[h.chunk_id][1],
                 "page_start": by_id[h.chunk_id][2], "page_end": by_id[h.chunk_id][3],
                 "text": by_id[h.chunk_id][4], "project_id": by_id[h.chunk_id][5],
                 "doc_type": by_id[h.chunk_id][6],
                 **({"meta": by_id[h.chunk_id][7]} if by_id[h.chunk_id][7] else {})} for h in found]
        stages.append({"id": "retrieve", "label": "Find the closest", "duration_ms": _ms(t),
                       "detail": f"top {wanted} from the {run[0]} library ({run[1]}/{run[2]})"})

        ranking = None
        if ranked:
            t = time.perf_counter()
            hits, ranking = rank(question, hits, top=k)
            stages.append({"id": "rank", "label": "Sort by the stat asked for", "duration_ms": _ms(t),
                           "detail": ranking["understood"] if ranking["applied"]
                           else f"{ranking['understood']}: kept the order search gave"})

        t = time.perf_counter()
        sources, dropped = assemble(hits)
        stages.append({"id": "assemble", "label": "Pick what the AI reads", "duration_ms": _ms(t),
                       "detail": f"{len(sources)} kept, {len(dropped)} dropped"})

        t = time.perf_counter()
        gen = generate(question, sources, library=run[0],
                       sorted_by=ranking["understood"] if ranking and ranking["applied"] else None)
        stages.append({"id": "generate", "label": "Write the answer", "duration_ms": _ms(t),
                       "detail": gen.get("skipped") or f"{gen.get('output_tokens')} tokens from {gen['model']}"})

        t = time.perf_counter()
        verdict = check(gen.get("answer"), [s.label for s in sources])
        stages.append({"id": "check", "label": "Check the citations", "duration_ms": _ms(t),
                       "detail": "passed" if verdict["passed"] else "; ".join(verdict["problems"])})

        trace = {
            "trace_id": str(uuid.uuid4()), "question": question, "library": run[0], "stages": stages,
            "retrieval": {"query_vector": [round(float(x), 4) for x in q], "hits": hits},
            **({"rank": ranking} if ranking else {}),
            "sources": [s.__dict__ for s in sources], "dropped": dropped,
            "answer": gen.get("answer"), "generation": gen, "check": verdict,
        }
        t = time.perf_counter()
        conn.execute("insert into traces (id, library, question, trace) values (%s, %s, %s, %s)",
                     (trace["trace_id"], run[0], question, Jsonb(trace)))
        conn.commit()
        stages.append({"id": "log", "label": "Log the trace", "duration_ms": _ms(t), "detail": "saved"})
    return trace
