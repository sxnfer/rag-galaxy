"""The electric car library: a table checked on load, turned into word cards, then sorted by a rank stage."""

import pytest

from pipeline.answer.assemble import assemble
from pipeline.answer.generate import system_prompt, user_message
from pipeline.answer.rank import Intent, find_make, parse_intent, rank
from pipeline.chunk.cards import bucket, car_cards, class_best, ordinal, rank_phrase
from pipeline.collect.table import COLUMNS, TableError, load, parse_table
from pipeline.evaluate.run import in_order, load_golden
from pipeline.libraries import LIBRARIES

CSV = LIBRARIES["ev"]["table"]
HEADER = ",".join(COLUMNS)


def table(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


# name, make, model, class, drive, year, range, city, highway, MPGe, kWh/100mi, 240 V hours, $/year, EPA id
GOOD = "Kia Niro Electric,Kia,Niro Electric,Small SUV,FWD,2026,253,275,226,113,30.0,7.5,700,50001"


# --- collect/table.py: the checks on load ---

def test_the_committed_table_loads_and_is_consistent():
    cars = load(CSV)
    assert 150 <= len(cars) <= 400
    assert cars[0]["row"] == 2                       # the header is row 1, as in a spreadsheet
    assert len({c["name"].lower() for c in cars}) == len(cars)
    assert {"Small car", "SUV", "Small SUV", "Pickup"} <= {c["class"] for c in cars}
    assert {c["year"] for c in cars} == {2026}


def test_numbers_become_numbers_and_blanks_become_none():
    c = parse_table(table(GOOD.replace(",7.5,", ",,")))[0]
    assert c["range_mi"] == 253 and isinstance(c["range_mi"], int)
    assert c["kwh_per_100mi"] == 30.0 and c["charge_240v_h"] is None
    assert c["row"] == 2 and c["make"] == "Kia"


@pytest.mark.parametrize("rows, complaint", [
    ([GOOD, GOOD.replace(",253,", ",x,").replace("Kia Niro Electric", "Kia Niro 2")], "row 3 (Kia Niro 2): range_mi is 'x', not a number"),
    ([GOOD, "kia niro electric" + GOOD[17:]], "row 3 (kia niro electric): the name is already used in row 2"),
    ([GOOD.replace(",Small SUV,", ",Hovercraft,")], "row 2 (Kia Niro Electric): class 'Hovercraft'"),
    ([GOOD.replace(",FWD,", ",2WD,")], "row 2 (Kia Niro Electric): drive '2WD'"),
    ([GOOD.replace(",253,", ",5000,")], "row 2 (Kia Niro Electric): range_mi is 5000, outside 30 to 1000"),
    ([GOOD.replace(",253,", ",,")], "row 2 (Kia Niro Electric): range_mi is empty"),
    ([GOOD.replace(",113,", ",113.5,")], "row 2 (Kia Niro Electric): mpge is 113.5, but it must be a whole number"),
    ([GOOD.replace(",113,", ",150,")], "row 2 (Kia Niro Electric): mpge 150 doesn't match kwh_per_100mi 30.0"),
    ([], "no rows"),
])
def test_a_bad_table_fails_loudly_with_the_row_number(rows, complaint):
    with pytest.raises(TableError) as e:
        parse_table(table(*rows))
    assert complaint in str(e.value)


def test_a_missing_column_is_named():
    with pytest.raises(TableError, match="missing column.*epa_id"):
        parse_table("\n".join([HEADER.replace(",epa_id", ""), GOOD.rsplit(",", 1)[0]]))


# --- chunk/cards.py: buckets and rank phrases ---

def test_bucket_edges_come_from_percentiles():
    values = list(range(1, 11))                         # ten cars, 1..10
    assert [bucket(v, values) for v in values] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    assert bucket(1000, values + [1000]) == 4            # the top value is always "very high"
    assert bucket(5, [5, 5, 5, 5]) == 2                  # everyone equal: average
    assert bucket(3, [1, None, 3, None, 5]) == 2         # blanks aren't counted


def test_ordinals():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 103)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "103rd"]


def test_rank_phrases_count_from_the_nearer_end():
    values = [100, 200, 300, 400, 500, 600]
    assert rank_phrase(600, values, "cars", "longest range", "shortest range") == "longest range of 6 cars"
    assert rank_phrase(400, values, "cars", "longest range", "shortest range") == "3rd longest range of 6 cars"
    assert rank_phrase(200, values, "cars", "longest range", "shortest range") == "2nd shortest range of 6 cars"


def test_rank_phrases_where_small_is_good():
    costs = [550, 600, 700, 900, 1500]
    assert rank_phrase(550, costs, "cars", "cheapest to run", "most expensive to run", higher_is_top=False) \
        == "cheapest to run of 5 cars"
    assert rank_phrase(1500, costs, "cars", "cheapest to run", "most expensive to run", higher_is_top=False) \
        == "most expensive to run of 5 cars"


def test_ties_share_a_place_and_say_joint():
    values = [500, 400, 400, 300, 100, 50, 10]
    assert rank_phrase(400, values, "cars") == "joint 2nd highest of 7 cars"
    assert rank_phrase(300, values, "cars") == "4th highest of 7 cars"   # two cars tie above it
    assert rank_phrase(30, [10, None, 30, None], "cars") == "highest of 2 cars"   # blanks aren't counted


def test_class_best_only_speaks_for_the_leader():
    assert class_best(420, [300, 420, 350], "Pickup", "longest range") == "longest range among pickup trucks"
    assert class_best(350, [300, 420, 350], "Pickup", "longest range") is None
    assert class_best(420, [420, 420], "Pickup", "longest range") == "joint longest range among pickup trucks"
    assert class_best(6.0, [6.0, 9.5], "Small SUV", "fastest to charge", higher_is_top=False) \
        == "fastest to charge among small SUVs"
    assert class_best(174, [174], "Two-seater", "longest range") is None   # a class of one has nothing to lead


# --- chunk/cards.py: the cards themselves ---

@pytest.fixture(scope="module")
def cars():
    return load(CSV)


@pytest.fixture(scope="module")
def cards(cars):
    return car_cards(cars)


def by(cards, name, facet):
    return next((c for c in cards if c.meta["item"] == name and c.meta["facet"] == facet), None)


def test_one_card_per_facet_with_breadcrumb_row_and_numbers(cards):
    niro = [c for c in cards if c.meta["item"] == "Kia Niro Electric"]
    assert [c.meta["facet"] for c in niro] == ["overview", "range", "efficiency", "cost", "charging"]
    r = by(cards, "Kia Niro Electric", "range")
    assert r.breadcrumb == "Electric cars › Small SUV › Kia Niro Electric › Range"
    assert r.page_start == r.page_end == r.meta["row"]
    assert r.meta["class"] == "Small SUV" and r.meta["make"] == "Kia" and r.meta["drive"] == "FWD"
    assert r.meta["stats"]["range_mi"] == 253
    assert "range: 253 miles on a full charge" in r.text and "275 miles in the city" in r.text


def test_superlatives_are_written_into_the_words(cards):
    assert "512 miles on a full charge (very long), longest range of 231 cars and longest range among large cars" \
        in by(cards, "Lucid Air G Touring XR AWD", "range").text
    assert "shortest range of 231 cars" in by(cards, "Fiat 500e", "range").text
    assert "least efficient of 231 cars" in by(cards, "Bugatti Rimac Nevera R", "efficiency").text
    assert "fastest to charge of 231 cars and fastest to charge among small SUVs" \
        in by(cards, "Toyota bZ (energy capacity 200 Ah)", "charging").text


def test_cost_words_point_the_right_way(cards):
    """A big yearly bill is "expensive", a small one "cheap", on the card and in the overview alike."""
    bugatti = by(cards, "Bugatti Rimac Nevera R", "cost").text
    assert "$1,500 a year" in bugatti and "(very expensive), most expensive to run of 231 cars" in bugatti
    model3 = by(cards, "Tesla Model 3 Standard RWD", "cost").text
    assert "(very cheap), joint 2nd cheapest to run" in model3
    assert "very cheap to run" in by(cards, "Tesla Model 3 Standard RWD", "overview").text
    assert "very expensive to run" in by(cards, "Bugatti Rimac Nevera R", "overview").text


def test_a_missing_number_means_no_card_not_a_made_up_sentence():
    rows = [GOOD, GOOD.replace("Kia Niro Electric", "Bare").replace(",275,226,", ",,,").replace(",7.5,", ",,")]
    made = car_cards(parse_table(table(*rows)))
    bare = [c for c in made if c.meta["item"] == "Bare"]
    assert [c.meta["facet"] for c in bare] == ["overview", "range", "efficiency", "cost"]   # no charging figure
    assert "in the city" not in next(c.text for c in bare if c.meta["facet"] == "range")
    assert "home charging" not in bare[0].text
    assert "None" not in " ".join(c.text for c in made)


# --- answer/rank.py: reading the intent ---

MAKES = {"Tesla", "Mercedes-Benz", "Chevrolet", "Rivian", "Hyundai", "MINI"}


@pytest.mark.parametrize("question, stat, best, cls, make, drive, understood", [
    ("longest range electric SUV", "range", True, "SUV", None, None, "SUV · range · longest"),
    ("most efficient small car", "efficiency", True, "small car", None, None, "small car · efficiency · most efficient"),
    ("cheapest electric pickup to run", "cost", True, "pickup", None, None, "pickup · running cost · cheapest"),
    ("least expensive truck to run", "cost", True, "pickup", None, None, "pickup · running cost · cheapest"),
    ("most expensive electric car to run", "cost", False, None, None, None, "running cost · most expensive"),
    ("shortest range EV", "range", False, None, None, None, "range · shortest"),
    ("least efficient SUV", "efficiency", False, "SUV", None, None, "SUV · efficiency · least efficient"),
    ("uses the least energy", "efficiency", True, None, None, None, "efficiency · most efficient"),
    ("fastest charging small SUV", "charging", True, "small SUV", None, None, "small SUV · charging time · fastest"),
    ("which pickup truck takes longest to charge?", "charging", False, "pickup", None, None, "pickup · charging time · slowest"),
    ("which Rivian goes the furthest on a charge?", "range", True, None, "Rivian", None, "Rivian · range · longest"),
    ("most efficient AWD SUV", "efficiency", True, "SUV", None, "AWD", "AWD · SUV · efficiency · most efficient"),
    ("most efficient Mercedes", "efficiency", True, None, "Mercedes-Benz", None, "Mercedes-Benz · efficiency · most efficient"),
    ("cheapest Chevy to run", "cost", True, None, "Chevrolet", None, "Chevrolet · running cost · cheapest"),
    ("big SUV with the most range", "range", True, "large SUV", None, None, "large SUV · range · longest"),
])
def test_intent_is_read_with_plain_rules(question, stat, best, cls, make, drive, understood):
    i = parse_intent(question, MAKES)
    assert (i.stat, i.best_end, i.item_class, i.make, i.drive) == (stat, best, cls, make, drive)
    assert i.understood() == understood


@pytest.mark.parametrize("question", ["a roomy electric car for a big family",
                                      "which electric car has the best safety rating?",
                                      "what is the top speed of the Porsche Taycan Turbo GT?"])
def test_no_stat_word_means_no_intent(question):
    assert parse_intent(question, MAKES).stat is None


def test_a_make_is_only_found_as_a_whole_word():
    assert find_make("longest range tesla", MAKES) == "Tesla"  # any case
    assert find_make("a mini suv", MAKES) is None              # "mini" is also a word...
    assert find_make("cheapest MINI to run", MAKES) == "MINI"  # ...so the make needs its capitals
    assert find_make("teslas are fun", MAKES) is None          # not part of a longer word
    assert find_make("most efficient car", MAKES) is None


def test_which_way_to_sort():
    assert Intent("range", best_end=True).descending            # longest range: big first
    assert not Intent("range", best_end=False).descending
    assert not Intent("cost", best_end=True).descending         # cheapest: small first
    assert Intent("cost", best_end=False).descending
    assert not Intent("charging", best_end=True).descending     # fastest to charge: fewest hours first
    assert Intent("efficiency").column == "mpge" and Intent("charging").facet == "charging"


# --- answer/rank.py: the ordering ---

def as_hits(cards, score=lambda i: 0.5):
    return [{"chunk_id": i, "score": score(i), "text": c.text, "breadcrumb": c.breadcrumb,
             "page_start": c.page_start, "page_end": c.page_end, "meta": c.meta} for i, c in enumerate(cards)]


def names(hits):
    return [h["meta"]["item"] for h in hits]


def test_rank_sorts_the_candidates_by_the_stat(cards):
    kept, report = rank("which electric car has the longest range?", as_hits(cards), top=5)
    assert names(kept)[:2] == ["Lucid Air G Touring XR AWD", "Chevrolet Silverado EV Max Range WT"]
    assert len(kept) == 5 and all(h["meta"]["facet"] == "range" for h in kept)   # the facet that holds the stat
    assert report["applied"] and report["understood"] == "range · longest"
    assert report["items"][0] == {"item": "Lucid Air G Touring XR AWD", "value": 512, "unit": "miles",
                                  "chunk_id": kept[0]["chunk_id"]}


def test_rank_keeps_to_the_class_and_sorts_small_first_where_small_is_good(cards):
    kept, _ = rank("fastest charging small SUV", as_hits(cards), top=3)
    assert all(h["meta"]["class"] == "Small SUV" for h in kept)
    hours = [h["meta"]["stats"]["charge_240v_h"] for h in kept]
    assert hours == sorted(hours) and names(kept)[0] == "Toyota bZ (energy capacity 200 Ah)"


def test_plain_suv_covers_small_suvs_too(cards):
    kept, _ = rank("most efficient SUV", as_hits(cards), top=10)
    assert {h["meta"]["class"] for h in kept} <= {"SUV", "Small SUV"}
    assert "Small SUV" in {h["meta"]["class"] for h in kept}


def test_rank_only_sees_what_search_returned(cards):
    """It sorts the candidates, it doesn't search: a car that wasn't retrieved can't win."""
    some = [h for h in as_hits(cards) if h["meta"]["item"] in ("Kia Niro Electric", "Fiat 500e")]
    kept, _ = rank("which electric car has the longest range?", some, top=5)
    assert names(kept) == ["Kia Niro Electric", "Fiat 500e"]


def test_ties_go_to_the_better_match_then_the_name(cards):
    tied = [by(cards, n, "cost") for n in ("Lucid Air G Touring XR AWD", "Toyota bZ (energy capacity 200 Ah)")]  # both $600
    hits = as_hits(tied)
    assert names(rank("cheapest to run", hits)[0]) == ["Lucid Air G Touring XR AWD", "Toyota bZ (energy capacity 200 Ah)"]
    hits[1]["score"] = 0.9
    assert names(rank("cheapest to run", hits)[0]) == ["Toyota bZ (energy capacity 200 Ah)", "Lucid Air G Touring XR AWD"]


def test_no_stat_word_keeps_the_order_search_gave(cards):
    hits = as_hits(cards)[:20]
    kept, report = rank("a roomy electric car for a big family", hits, top=5)
    assert kept == hits[:5]
    assert not report["applied"] and report["items"] == [] and report["candidates"] == 20
    assert [b["chunk_id"] for b in report["before"]] == list(range(20))   # search's own order, for the trace


def test_rank_falls_back_when_search_missed_the_facet(cards):
    hits = as_hits([by(cards, n, "overview") for n in ("Kia Niro Electric", "Fiat 500e")])
    kept, report = rank("which electric car has the longest range?", hits)
    assert names(kept) == ["Kia Niro Electric", "Fiat 500e"] and report["applied"]   # every card carries the numbers


# --- the golden set, the prompt and the context ---

def test_golden_cars_exist_and_match_the_table(cars, cards):
    """With perfect retrieval (every card a candidate), the rank stage must return exactly the expected cars.
    This keeps golden.yaml, the CSV and the intent rules honest with each other."""
    known = {c["name"] for c in cars}
    golden = [q for q in load_golden() if q.get("library") == "ev"]
    assert len(golden) >= 20 and sum(not q.get("answerable", True) for q in golden) == 2
    hits = as_hits(cards)
    makes = {c["make"] for c in cars}
    for q in golden:
        if not q.get("answerable", True):
            assert parse_intent(q["question"], makes).stat is None, q["id"]
            continue
        assert set(q["items"]) <= known, q["id"]
        assert parse_intent(q["question"], makes).stat, q["id"]
        kept, _ = rank(q["question"], hits, top=len(q["items"]))
        assert set(names(kept)) == set(q["items"]), q["id"]


def test_assemble_keeps_different_cars_and_cites_rows(cards):
    """Cards share a template, so word overlap would call different cars duplicates. They're compared by car and facet."""
    niro, fiat = by(cards, "Kia Niro Electric", "range"), by(cards, "Fiat 500e", "range")
    kept, dropped = assemble(as_hits([niro, fiat, niro]))
    assert [s.label for s in kept] == ["S1", "S2"] and kept[0].pages == f"row {niro.meta['row']}"
    assert dropped == [{"chunk_id": 2, "reason": "duplicate"}]


def test_the_ev_prompt_asks_for_a_ranked_list_and_keeps_the_rules(cards):
    ev, other = system_prompt("ev"), system_prompt("some-other-library")
    assert "numbered list" in ev and "purchase prices" in ev and "numbered list" not in other
    for p in (ev, other):
        assert "Use only the numbered sources" in p and "NOT_FOUND" in p
    niro = by(cards, "Kia Niro Electric", "range")
    sources, _ = assemble(as_hits([niro]))
    msg = user_message("longest range", sources, sorted_by="range · longest")
    assert f"[S1] Electric cars › Small SUV › Kia Niro Electric › Range (row {niro.meta['row']})" in msg
    assert "already sorted for this question (range · longest)" in msg
    assert "already sorted" not in user_message("longest range", sources)


def test_in_order_keeps_first_appearance():
    assert in_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
