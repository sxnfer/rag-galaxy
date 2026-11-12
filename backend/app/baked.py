"""
Pre-computed answers for the example questions on the home page.

Most visitors click an example rather than typing. Running those through the
whole pipeline every time would cost money and add nothing new, so we run
each one once, ahead of time (`python -m pipeline bake --library L`), save the
full trace, and replay it. The app says plainly that it is a replay.

Each library has its own file, app/baked/<library>.json, and its own example
questions (in pipeline/libraries.py).

A saved trace points at chunk ids. If the chunks are rebuilt (new chunker,
new size, new documents), those ids change and the replay would light up the
wrong stars. So on startup every saved trace is checked against the current
library; any that no longer match are ignored until you bake again.
"""

import copy
import json
from pathlib import Path

import numpy as np

from pipeline.libraries import LIBRARIES

from .guard import AnswerCache

BAKED_DIR = Path(__file__).parent / "baked"


def baked_file(library: str) -> Path:
    return BAKED_DIR / f"{library}.json"


def load(run, galaxy) -> dict[str, dict]:
    """Saved traces that still match the live library, keyed by question. run[0] is the library."""
    f = baked_file(run[0])
    if not f.exists():
        print(f"[{run[0]}] no pre-computed examples ({f.name} missing): run `python -m pipeline bake --library {run[0]}`")
        return {}
    data = json.loads(f.read_text())
    if tuple(data.get("run", [])) != tuple(run):
        print(f"[{run[0]}] pre-computed examples were made for run {data.get('run')}, not {list(run)}: ignored. Bake again.")
        return {}
    known = {row[0] for row in galaxy.rows}
    good = {}
    for trace in data.get("traces", []):
        ids = [h["chunk_id"] for h in trace["retrieval"]["hits"]]
        if not all(i in known for i in ids):
            print(f"[{run[0]}] pre-computed example is stale (chunks changed), ignored: {trace['question']!r}")
            continue
        good[AnswerCache.key(trace["question"])] = trace
    print(f"[{run[0]}] loaded {len(good)} pre-computed examples")
    return good


def replay(baked: dict[str, dict], question: str, galaxy) -> dict | None:
    trace = baked.get(AnswerCache.key(question))
    if trace is None:
        return None
    trace = copy.deepcopy(trace)
    trace["replay"] = True
    # The 3D layout can change when the library is reloaded, so place the question fresh.
    trace["retrieval"]["query_position"] = galaxy.project(np.array(trace["retrieval"]["query_vector"]))
    return trace


def examples(library: str, baked: dict[str, dict]) -> list[dict]:
    """What the home page shows: every example, and whether it has a written answer."""
    out = []
    for q in LIBRARIES[library]["examples"]:
        t = baked.get(AnswerCache.key(q))
        out.append({"question": q, "ready": t is not None, "answered": bool(t and t.get("answer"))})
    return out
