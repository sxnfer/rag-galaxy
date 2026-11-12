"""
Post-checks before an answer is shown.

  1. Every citation must point to a source we actually gave the model.
     A citation like [S7] when we sent S1-S4 is invented.
  2. A factual answer must cite something. An uncited answer is ungrounded.
  3. NOT_FOUND is a valid, honest answer and passes.
(Checking that each cited source really supports its sentence, "groundedness",
 needs an LLM judge and comes later.)
"""

import re

from .generate import NOT_FOUND

CITE = re.compile(r"\[(S\d+)\]")


def check(answer: str | None, labels: list[str]) -> dict:
    if answer is None:
        return {"passed": False, "problems": ["no answer generated"], "cited": []}
    if answer.strip() == NOT_FOUND:
        return {"passed": True, "problems": [], "cited": [], "not_found": True}
    cited = sorted(set(CITE.findall(answer)), key=lambda s: int(s[1:]))
    problems = [f"cites {c}, which was not provided" for c in cited if c not in labels]
    if not cited:
        problems.append("no citations")
    return {"passed": not problems, "problems": problems, "cited": cited}
