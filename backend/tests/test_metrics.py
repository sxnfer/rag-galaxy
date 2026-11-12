from pipeline.evaluate.metrics import recall_at_k, reciprocal_rank


def test_reciprocal_rank():
    assert reciprocal_rank([4, 7, 9], {7}) == 0.5
    assert reciprocal_rank([7, 4], {7, 4}) == 1.0
    assert reciprocal_rank([1, 2, 3], {9}) == 0.0


def test_recall_at_k_only_counts_the_top_k():
    assert recall_at_k([1, 2, 3, 4, 5, 6], {6}, 5) == 0.0
    assert recall_at_k([6, 2, 3], {6}, 5) == 1.0
