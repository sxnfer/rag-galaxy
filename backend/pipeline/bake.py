"""
`python -m pipeline bake --library L`: run every home-page example for one
library once and save the traces, so the live site can replay them without
calling the AI (see app/baked.py).

Run it after chunking, with ANTHROPIC_API_KEY set so the answers are written.
Without a key the search part is still saved, and the answer says it is missing.
Then restart the API.
"""

import json
import os
from datetime import datetime, timezone

from app.baked import baked_file
from app.embedder import load_embedder

from .answer.pipeline import answer
from .libraries import LIBRARIES, check


def run(library: str, chunker: str, size: int) -> None:
    questions = LIBRARIES[check(library)]["examples"]
    if not questions:
        raise SystemExit(f"No example questions for {library!r} yet: add them in pipeline/libraries.py")
    emb = load_embedder()
    the_run = (library, chunker, size, emb.name)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Note: ANTHROPIC_API_KEY is not set, so the examples get no written answer.")
    traces = []
    for q in questions:
        t = answer(q, emb, the_run)
        verdict = "NOT_FOUND" if t["check"].get("not_found") else ("passed" if t["check"]["passed"] else "FAILED")
        top = t["retrieval"]["hits"][0] if t["retrieval"]["hits"] else None
        print(f"- {q}\n    top hit {top['score'] if top else '-'} from {top['project_id'] if top else '-'}; "
              f"answer: {'yes' if t.get('answer') else 'no'}; check: {verdict}")
        traces.append(t)
    f = baked_file(library)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": list(the_run),
        "traces": traces,
    }, indent=1, default=str))
    print(f"Saved {len(traces)} examples to {f}. Restart the API to use them.")
