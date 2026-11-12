"""
M4 runner: score every run (chunker x size) on the golden set.

For each answerable question we embed it with the run's model, retrieve the
top k, and mark a chunk relevant when it belongs to the right document and its
pages overlap the answer pages. Results print as a Markdown table and are
saved to data/eval/ (latest.json is always the newest).

A table library (the electric cars) is scored on cars instead of pages, twice:
"cards" is search alone, "cards + rank" adds the rank stage. The gap between
the two rows is what sorting by the stat is worth.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from app.embedder import load_embedder

from ..config import DATA
from ..db import connect
from ..answer.rank import CANDIDATES, rank
from ..chunk.search import search
from ..libraries import DEFAULT_CLI_LIBRARY, LIBRARIES
from .metrics import reciprocal_rank, recall_at_k

GOLDEN = Path(__file__).parent / "golden.yaml"
EVAL_DIR = DATA / "eval"


def load_golden(path: Path = GOLDEN) -> list[dict]:
    items = yaml.safe_load(path.read_text()) or []
    ids = [q["id"] for q in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids in golden set")
    return items


def relevant_ids(conn, q: dict, run) -> set[int]:
    rows = conn.execute(
        """select c.id from chunks c join manifest m on m.sha256 = c.doc_sha256
           where c.library=%s and c.chunker=%s and c.chunk_size=%s and c.model=%s
             and m.project_id=%s and m.doc_type=%s
             and c.page_start <= %s and c.page_end >= %s""",
        (*run, q["project_id"], q["doc_type"], max(q["pages"]), min(q["pages"]))).fetchall()
    return {r[0] for r in rows}


def in_order(names: list[str]) -> list[str]:
    """Each name once, keeping the place where it first appeared."""
    return list(dict.fromkeys(names))


def item_lists(conn, question: str, qvec, run, method: str = "exact") -> dict[str, list[str]]:
    """For a table library: the cars search alone returns, and the cars after the rank stage.
    Both start from the same candidates, so the only difference is the sorting."""
    found = search(conn, qvec, run, k=CANDIDATES, method=method)
    conn.rollback()
    meta = dict(conn.execute("select id, meta from chunks where id = any(%s)", ([h.chunk_id for h in found],)).fetchall())
    hits = [{"chunk_id": h.chunk_id, "score": h.score, "meta": meta[h.chunk_id]} for h in found]
    ranked, _ = rank(question, hits, top=CANDIDATES)
    return {"cards": in_order([h["meta"]["item"] for h in hits]),
            "cards + rank": in_order([h["meta"]["item"] for h in ranked])}


def score_items(conn, asked: list[dict], qvecs: dict, run_key, k: int, method: str) -> list[dict]:
    """One result row per stage ("cards", "cards + rank") for a table library."""
    scores: dict[str, tuple[list, list]] = {}
    for q in asked:
        expected = set(q["items"])
        for stage, names in item_lists(conn, q["question"], qvecs[q["id"]], run_key, method).items():
            recalls, rrs = scores.setdefault(stage, ([], []))
            recalls.append(recall_at_k(names, expected, k))
            rrs.append(reciprocal_rank(names, expected))
    return [{"library": run_key[0], "chunker": run_key[1], "size": run_key[2], "model": run_key[3],
             "k": k, "method": method, "stage": stage, "scored_on": "items", "questions": len(asked),
             f"recall@{k}": float(np.mean(recalls)), "mrr": float(np.mean(rrs)), "no_relevant_chunks": []}
            for stage, (recalls, rrs) in scores.items()]


def runs_available(conn) -> list[tuple[str, str, int, str]]:
    return conn.execute("select distinct library, chunker, chunk_size, model from chunks order by 1, 2, 3").fetchall()


def run(k: int = 5, method: str = "exact") -> list[dict]:
    golden = [q for q in load_golden() if q.get("answerable", True)]
    if not golden:
        raise SystemExit(f"The golden set is empty: write questions in {GOLDEN}")
    embedder = load_embedder()
    qvecs = {q["id"]: (v := embedder.embed_query(q["question"])) / np.linalg.norm(v) for q in golden}
    results = []
    with connect() as conn:
        for run_key in runs_available(conn):
            if run_key[3] != embedder.name:
                print(f"  skipping {run_key}: embedded with a different model (same-model rule)")
                continue
            recalls, rrs, missing = [], [], []
            asked = [q for q in golden if q.get("library", DEFAULT_CLI_LIBRARY) == run_key[0]]  # each library has its own questions
            if not asked:
                continue
            if LIBRARIES.get(run_key[0], {}).get("rank"):
                results += score_items(conn, asked, qvecs, run_key, k, method)
                continue
            for q in asked:
                rel = relevant_ids(conn, q, run_key)
                if not rel:
                    missing.append(q["id"])  # the answer pages produced no chunks (scanned? flagged?)
                ranked = [h.chunk_id for h in search(conn, qvecs[q["id"]], run_key, k=max(k, 10), method=method)]
                conn.rollback()
                recalls.append(recall_at_k(ranked, rel, k))
                rrs.append(reciprocal_rank(ranked, rel))
            results.append({
                "library": run_key[0], "chunker": run_key[1], "size": run_key[2], "model": run_key[3],
                "k": k, "method": method, "questions": len(asked), f"recall@{k}": float(np.mean(recalls)), "mrr": float(np.mean(rrs)),
                "no_relevant_chunks": missing,
            })
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"created_at": stamp, "results": results}
    (EVAL_DIR / f"{stamp}.json").write_text(json.dumps(out, indent=2))
    (EVAL_DIR / "latest.json").write_text(json.dumps(out, indent=2))
    print(f"\n| library | run | recall@{k} | MRR | questions |\n|---|---|---|---|---|")
    for r in results:
        name = r.get("stage") or f"{r['chunker']}/{r['size']}"  # a table library's two rows are named by stage
        print(f"| {r['library']} | {name} | {r[f'recall@{k}']:.3f} | {r['mrr']:.3f} | {r['questions']} |")
    return results
