from pipeline.answer.assemble import assemble
from pipeline.answer.check import check


def hit(i, text, score=0.5):
    return {"chunk_id": i, "text": text, "score": score, "breadcrumb": f"P > PDD > s{i}", "page_start": i, "page_end": i}


def test_assemble_drops_duplicates_and_labels_sources():
    kept, dropped = assemble([hit(1, "the wind farm has 30 turbines"), hit(2, "the wind farm has 30 turbines"),
                              hit(3, "methodology ACM0002 version 12")])
    assert [s.label for s in kept] == ["S1", "S2"] and dropped[0]["reason"] == "duplicate"


def test_assemble_respects_budget():
    kept, dropped = assemble([hit(i, f"word{i} " * 400) for i in range(5)], budget_words=1000)
    assert len(kept) == 2 and all(d["reason"] == "over budget" for d in dropped)


def test_check_catches_invented_and_missing_citations():
    assert check("It has 30 turbines [S1].", ["S1", "S2"])["passed"]
    assert not check("It has 30 turbines [S7].", ["S1", "S2"])["passed"]
    assert not check("It has 30 turbines.", ["S1"])["passed"]
    assert check("NOT_FOUND", ["S1"])["passed"]
