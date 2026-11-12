"""
Retrieval metrics. For each golden question we know which chunks count as
"relevant" (they come from the right document and overlap the right pages).
The search returns a ranked list. These functions score that list.
"""


# ---------------------------------------------------------------------------
# San wrote these (M4 core functions).
#
# ranked:   the retrieved chunk ids, best first, e.g. [41, 7, 93, 12, 5]
# relevant: the set of chunk ids that would answer the question, e.g. {7, 8}
#
# recall_at_k: of the relevant chunks, what share appear in the top k?
#   (Some teams instead score 1 if ANY relevant chunk is in the top k, "hit
#    rate". Decide which you mean, write it in the docstring, and be ready to
#    say why in an interview.)
# mrr: reciprocal rank of the FIRST relevant chunk: 1 if it's first, 1/2 if
#   second, 1/3 if third... and 0 if none is retrieved. (The "mean" in MRR is
#   taken over all questions by the runner, not here.)
# Edge cases to decide: relevant is empty (an unanswerable question).
# Tests that describe "done": tests/test_metrics.py.
# ---------------------------------------------------------------------------
def recall_at_k(ranked: list[int], relevant: set[int], k: int = 5) -> float:
    """Share of the relevant chunks that appear in the top k (true recall, not hit rate).
    An unanswerable question (no relevant chunks) scores 0.0; the runner reports those separately."""
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: list[int], relevant: set[int]) -> float:
    """1 / position of the first relevant chunk (1-based), or 0.0 if none was retrieved."""
    for position, chunk_id in enumerate(ranked, start=1):
        if chunk_id in relevant:
            return 1.0 / position
    return 0.0
