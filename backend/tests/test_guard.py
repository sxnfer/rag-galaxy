"""The public-demo protection: rate limits, the daily AI budget, the answer cache, saved examples."""

import json

import pytest

from app import baked
from app.guard import AnswerCache, Guard, Limited, visitor_id


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_per_minute_limit_then_recovers():
    clock = Clock()
    g = Guard(per_minute=2, per_day=100, daily_budget=100, clock=clock)
    g.check("a"); g.check("a")
    with pytest.raises(Limited) as e:
        g.check("a")
    assert 1 <= e.value.retry_after <= 61
    g.check("b")  # someone else is unaffected
    clock.t += 61
    g.check("a")  # a minute later, allowed again


def test_left_counts_down_and_recovers():
    clock = Clock()
    g = Guard(per_minute=2, per_day=5, daily_budget=100, clock=clock)
    assert g.left("a") == {"this_minute": 2, "today": 5}
    g.check("a")
    assert g.left("a") == {"this_minute": 1, "today": 4} and g.left("b") == {"this_minute": 2, "today": 5}
    clock.t += 61
    assert g.left("a") == {"this_minute": 2, "today": 4}


def test_per_day_limit():
    clock = Clock()
    g = Guard(per_minute=100, per_day=3, daily_budget=100, clock=clock)
    for _ in range(3):
        g.check("a"); clock.t += 61
    with pytest.raises(Limited):
        g.check("a")


def test_daily_budget_stops_everyone_and_resets_next_day():
    clock = Clock(86400 * 20 + 10)
    g = Guard(per_minute=100, per_day=100, daily_budget=2, clock=clock)
    g.spend(); g.spend()
    with pytest.raises(Limited):
        g.check("new visitor")
    clock.t += 86400
    g.check("new visitor")


def test_visitor_is_the_connection_when_there_is_no_proxy():
    # No proxy of our own: the header is whatever the sender typed, so it is ignored.
    assert visitor_id("203.0.113.9", "1.2.3.4", proxies=0) == "203.0.113.9"
    assert visitor_id(None, None, proxies=0) == "unknown"


def test_visitor_behind_a_proxy_is_the_entry_the_proxy_wrote():
    # The proxy adds the real address at the end. Entries before it can be faked.
    assert visitor_id("10.0.0.1", "203.0.113.9", proxies=1) == "203.0.113.9"
    assert visitor_id("10.0.0.1", "6.6.6.6, 7.7.7.7, 203.0.113.9", proxies=1) == "203.0.113.9"
    assert visitor_id("10.0.0.1", None, proxies=1) == "10.0.0.1"   # no header: fall back to the connection


def test_ipv6_visitors_are_counted_by_their_block():
    a = visitor_id("2001:db8:1:2:aaaa::1", None, proxies=0)
    assert a == visitor_id("2001:db8:1:2:bbbb::2", None, proxies=0) == "2001:db8:1:2::/64"
    assert visitor_id("2001:db8:1:3::1", None, proxies=0) != a
    assert visitor_id("::ffff:203.0.113.9", None, proxies=0) == "203.0.113.9"   # IPv4 written the IPv6 way


def test_cache_ignores_case_spaces_and_question_mark():
    c = AnswerCache(size=2)
    c.put("Who validated Baguari?", {"answer": "SGS"})
    assert c.get("  who   validated baguari ")["answer"] == "SGS"
    c.put("q2", {}); c.put("q3", {})
    assert c.get("who validated baguari") is None  # oldest pushed out


class FakeGalaxy:
    def __init__(self, ids):
        self.rows = [(i,) for i in ids]

    def project(self, v):
        return [1.0, 2.0, 3.0]


def _write(tmp_path, monkeypatch, run, hit_ids):
    f = tmp_path / f"{run[0]}.json"
    trace = {"question": "longest range electric SUV", "answer": "1. Lucid Gravity GT [S1]",
             "retrieval": {"query_vector": [0.1] * 4, "hits": [{"chunk_id": i} for i in hit_ids]}}
    f.write_text(json.dumps({"run": list(run), "traces": [trace]}))
    monkeypatch.setattr(baked, "BAKED_DIR", tmp_path)


def test_baked_replay_is_marked_and_repositioned(tmp_path, monkeypatch):
    run = ("ev", "cards", 0, "m")
    _write(tmp_path, monkeypatch, run, [1, 2])
    g = FakeGalaxy([1, 2, 3])
    saved = baked.load(run, g)
    t = baked.replay(saved, "Longest range electric SUV", g)
    assert t["replay"] is True and t["retrieval"]["query_position"] == [1.0, 2.0, 3.0]
    assert baked.replay(saved, "something else", g) is None
    first = baked.LIBRARIES["ev"]["examples"][0]
    assert baked.examples("ev", saved)[0] == {"question": first, "ready": True, "answered": True}


def test_stale_baked_trace_is_ignored(tmp_path, monkeypatch):
    run = ("ev", "cards", 0, "m")
    _write(tmp_path, monkeypatch, run, [1, 99])  # chunk 99 no longer exists
    assert baked.load(run, FakeGalaxy([1, 2])) == {}


def test_baked_from_another_run_is_ignored(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, ("ev", "fixed", 300, "m"), [1])
    assert baked.load(("ev", "cards", 0, "m"), FakeGalaxy([1])) == {}


def test_each_library_reads_its_own_baked_file(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, ("ev", "cards", 0, "m"), [1])
    assert baked.load(("other", "cards", 0, "m"), FakeGalaxy([1])) == {}  # tmp_path has no other.json


class FakeLedger:
    """The database's part of the limits, as a dictionary: what survives a restart."""

    def __init__(self):
        self.rows = {}

    @staticmethod
    def who(day, visitor):
        return f"v:{visitor}"

    def counts(self, day, visitor):
        return self.rows.get((day, "site"), 0), self.rows.get((day, self.who(day, visitor)), 0)

    def add(self, day, who):
        self.rows[(day, who)] = self.rows.get((day, who), 0) + 1


def test_per_day_limit_survives_a_restart():
    ledger, now = FakeLedger(), [1000.0]
    clock = lambda: now[0]  # noqa: E731
    g = Guard(per_minute=100, per_day=3, daily_budget=100, clock=clock, ledger=ledger)
    for _ in range(3):
        g.check("1.2.3.4")
    # The server sleeps and starts again: a new Guard with nothing in memory, but the same ledger.
    g = Guard(per_minute=100, per_day=3, daily_budget=100, clock=clock, ledger=ledger)
    with pytest.raises(Limited):
        g.check("1.2.3.4")
    g.check("5.6.7.8")  # someone else is not affected
    assert g.left("5.6.7.8")["today"] == 2


def test_site_budget_survives_a_restart_and_resets_next_day():
    ledger, now = FakeLedger(), [1000.0]
    clock = lambda: now[0]  # noqa: E731
    g = Guard(per_minute=100, per_day=100, daily_budget=2, clock=clock, ledger=ledger)
    g.check("a"); g.spend()
    g.check("b"); g.spend()
    g = Guard(per_minute=100, per_day=100, daily_budget=2, clock=clock, ledger=ledger)  # restarted
    with pytest.raises(Limited):
        g.check("c")
    now[0] += 86400  # the next day
    g.check("c")


def test_ledger_never_stores_the_address_itself():
    from app.guard import Ledger

    who = Ledger.who(20000, "203.0.113.7")
    assert "203.0.113.7" not in who and len(who) == 32
    assert who != Ledger.who(20001, "203.0.113.7")  # a different fingerprint each day
