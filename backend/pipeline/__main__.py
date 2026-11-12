"""
Run one pipeline step:  python -m pipeline <step> [options]

Steps that work on one library take --library (default: ev, the electric cars).
A table library is not PDFs: register -> chunk -> hnsw -> bake, with no
parse step, and its run is always cards/0 (--chunker and --size are ignored).

  init-db                          create the tables (safe to re-run)
  register [--library L]           M1: hand-downloaded PDFs in the library's inbox -> manifest
                                   (ev: check data/seeds/ev/vehicles.csv and register it)
  parse [--force]                  M2: PDFs -> pages + quality reports
  chunk --chunker fixed --size 300 M3: chunk + embed + store one run (ev: one card per car and facet)
  hnsw --chunker fixed --size 300  M3: build the HNSW index for a run and measure its recall vs exact
  eval [--k 5]                     M4: score every run on the golden set
  ask "question"                   the full request path, printed
  bake [--chunker fixed --size 300] pre-compute the home-page examples (needs ANTHROPIC_API_KEY for answers)
"""

import argparse
import json

from .libraries import DEFAULT_CLI_LIBRARY, ORDER, is_table, run_of


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="step", required=True)
    sub.add_parser("init-db")
    r = sub.add_parser("register"); r.add_argument("--library", default=DEFAULT_CLI_LIBRARY, choices=ORDER)
    pr = sub.add_parser("parse"); pr.add_argument("--force", action="store_true")
    for name in ("chunk", "hnsw", "ask", "bake"):
        s = sub.add_parser(name)
        s.add_argument("--chunker", default="fixed", choices=["fixed", "structure"])
        s.add_argument("--size", type=int, default=300)
        s.add_argument("--library", default=DEFAULT_CLI_LIBRARY, choices=ORDER)
        if name == "chunk":
            s.add_argument("--overlap", type=int, default=50)
        if name == "ask":
            s.add_argument("question")
    e = sub.add_parser("eval"); e.add_argument("--k", type=int, default=5); e.add_argument("--method", default="exact")
    a = p.parse_args()
    if a.step in ("chunk", "hnsw", "ask", "bake"):
        a.chunker, a.size = run_of(a.library, a.chunker, a.size)

    if a.step == "init-db":
        from .db import init_db; init_db()
    elif a.step == "register":
        if is_table(a.library):
            from .collect.table import run; run(a.library)
        else:
            from .collect.register import run; run(a.library)
    elif a.step == "parse":
        from .parse.run import run; run(force=a.force)
    elif a.step == "chunk":
        from .chunk.build import run; run(a.library, a.chunker, a.size, a.overlap)
    elif a.step == "hnsw":
        _hnsw(a.library, a.chunker, a.size)
    elif a.step == "eval":
        from .evaluate.run import run; run(k=a.k, method=a.method)
    elif a.step == "bake":
        from .bake import run; run(a.library, a.chunker, a.size)
    elif a.step == "ask":
        from app.embedder import load_embedder
        from .answer.pipeline import answer
        emb = load_embedder()
        t = answer(a.question, emb, (a.library, a.chunker, a.size, emb.name))
        t["retrieval"].pop("query_vector")
        print(json.dumps(t, indent=2, default=str))


def _hnsw(library: str, chunker: str, size: int) -> None:
    """Build the index, then compare it with exact search using the golden questions
    (or, if there are none yet, 50 chunks used as stand-in queries)."""
    import time
    import numpy as np
    from app.embedder import load_embedder
    from .chunk.search import build_hnsw, hnsw_recall
    from .db import connect
    from .evaluate.run import load_golden

    emb = load_embedder()
    run = (library, chunker, size, emb.name)
    t = time.perf_counter(); build_hnsw(run); built = time.perf_counter() - t
    questions = [q["question"] for q in load_golden() if q.get("library", DEFAULT_CLI_LIBRARY) == library]
    if questions:
        queries = np.array([(v := emb.embed_query(q)) / np.linalg.norm(v) for q in questions]); source = "golden questions"
    else:
        with connect() as conn:
            rows = conn.execute("select embedding from chunks where library=%s and chunker=%s and chunk_size=%s "
                                "and model=%s order by random() limit 50", run).fetchall()
        from .db import as_np
        queries = np.array([as_np(r[0]) for r in rows]); source = "random chunks as queries"
    for ef in (10, 40, 100):
        r = hnsw_recall(run, queries, k=5, ef_search=ef)
        print(f"HNSW recall@5 vs exact, ef_search={ef}: {r:.3f}  ({len(queries)} {source})")
    print(f"Index built in {built:.2f}s")


if __name__ == "__main__":
    main()
