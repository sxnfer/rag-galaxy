"""
The cards chunker: turn one row of numbers into a few short passages of words.

An embedding model reads words. "Kia EV9, SUV, 304, 82, 41.0, 11.5, 900"
means nothing to it, and "longest range" can't be found by meaning if no
passage says "longest". So every number is written out twice:

  - a bucket: where it sits among all the cars (very low ... very high),
    taken from percentiles across the whole table, not hand-picked limits;
  - a rank phrase: "3rd longest range of 231 cars", "longest range among pickup trucks".

Each car becomes one card per facet (overview, range, efficiency, running
cost, charging), so a range question matches range cards and not a whole
stat sheet. Every card also carries the raw numbers (meta), which the rank
stage sorts by: see answer/rank.py.
"""

from dataclasses import dataclass, field

LIBRARY_LABEL = "Electric cars"

# class in the CSV -> (one of them, several of them)
CLASS_WORDS = {
    "Small car": ("small car", "small cars"),
    "Midsize car": ("midsize car", "midsize cars"),
    "Large car": ("large car", "large cars"),
    "Small SUV": ("small SUV", "small SUVs"),
    "SUV": ("SUV", "SUVs"),
    "Pickup": ("pickup truck", "pickup trucks"),
    "Wagon": ("station wagon", "station wagons"),
    "Minivan": ("minivan", "minivans"),
    "Two-seater": ("two-seater", "two-seaters"),
    "Van": ("van", "vans"),
}
DRIVE_WORDS = {"AWD": "all-wheel drive", "FWD": "front-wheel drive", "RWD": "rear-wheel drive"}

FACETS = {"overview": "Overview", "range": "Range", "efficiency": "Efficiency", "cost": "Running cost",
          "charging": "Charging"}

# The numbers every card carries, whatever its facet.
STATS = ("range_mi", "range_city_mi", "range_hwy_mi", "mpge", "kwh_per_100mi", "charge_240v_h", "annual_cost_usd")

# Five words per scale, from the bottom fifth of the table to the top fifth.
RANGE = ("very short", "short", "average", "long", "very long")
EFFICIENCY = ("very inefficient", "inefficient", "average", "efficient", "very efficient")
COST = ("very cheap", "cheap", "average", "expensive", "very expensive")
PACE = ("very slow", "slow", "average", "fast", "very fast")


@dataclass
class Card:
    text: str
    page_start: int      # the CSV row, so a citation points at the source
    page_end: int
    breadcrumb: str
    meta: dict = field(default_factory=dict)


def present(values) -> list[float]:
    return [v for v in values if v is not None]


def bucket(value: float, values: list[float]) -> int:
    """0 (bottom fifth of the table) to 4 (top fifth).

    The percentile is the share of cars below this value, counting ties as
    half below. Tied values therefore always land in the same bucket, and a
    table where every car is equal comes out as "average" (2)."""
    values = present(values)
    below = sum(v < value for v in values)
    equal = sum(v == value for v in values)
    percentile = (below + 0.5 * equal) / len(values)
    return min(4, int(percentile * 5))


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def rank_phrase(value: float, values: list[float], group: str, top: str = "highest", bottom: str = "lowest",
                higher_is_top: bool = True) -> str:
    """"3rd longest range of 231 cars", "joint 2nd cheapest to run of 26 pickup trucks".

    Counted from whichever end is nearer, so both "longest" and "shortest"
    questions find words to match. Ties share a place and say "joint".
    Where a small number is the good end (cost, charging time), pass
    higher_is_top=False with top="cheapest to run"."""
    values = present(values)
    more = sum(v > value for v in values)
    less = sum(v < value for v in values)
    tied = sum(v == value for v in values) > 1
    from_top, from_bottom = (more, less) if higher_is_top else (less, more)
    place, word = (from_top + 1, top) if from_top <= from_bottom else (from_bottom + 1, bottom)
    joint = "joint " if tied else ""
    nth = "" if place == 1 else f"{ordinal(place)} "
    return f"{joint}{nth}{word} of {len(values)} {group}"


def class_best(value: float, values_in_class: list[float], cls: str, top: str, higher_is_top: bool = True) -> str | None:
    """"longest range among pickup trucks" when this car leads its class, otherwise nothing."""
    values = present(values_in_class)
    if len(values) < 2:
        return None
    best = max(values) if higher_is_top else min(values)
    if value != best:
        return None
    joint = "joint " if sum(v == best for v in values) > 1 else ""
    return f"{joint}{top} among {CLASS_WORDS[cls][1]}"


def _num(x: float) -> str:
    """7.0 -> "7", 7.5 -> "7.5"."""
    return f"{x:g}"


class _Table:
    """The whole table, so one car's number can be compared with everyone else's."""

    def __init__(self, cars: list[dict]) -> None:
        self.cars = cars

    def col(self, stat: str, cls: str | None = None) -> list[float]:
        return present(c[stat] for c in self.cars if cls is None or c["class"] == cls)

    def level(self, c: dict, stat: str, words, low_is_good: bool = False) -> str:
        b = bucket(c[stat], self.col(stat))
        return words[4 - b if low_is_good else b]

    def ranked(self, c: dict, stat: str, top: str, bottom: str, higher_is_top: bool = True) -> str:
        """The rank among all cars, plus "... and longest range among SUVs" when it leads its class."""
        phrase = rank_phrase(c[stat], self.col(stat), "cars", top, bottom, higher_is_top)
        lead = class_best(c[stat], self.col(stat, c["class"]), c["class"], top, higher_is_top)
        return f"{phrase} and {lead}" if lead else phrase


def _who(c: dict) -> str:
    return f"{c['name']} ({CLASS_WORDS[c['class']][0]})"


def _overview_card(t: _Table, c: dict) -> str:
    one = CLASS_WORDS[c["class"]][0]
    traits = [f"{t.level(c, 'range_mi', RANGE)} range",
              t.level(c, "mpge", EFFICIENCY),
              f"{t.level(c, 'annual_cost_usd', COST)} to run"]
    if c["charge_240v_h"] is not None:
        traits.append(f"{t.level(c, 'charge_240v_h', PACE, low_is_good=True)} home charging")
    return (f"{c['name']} is a {c['year']} {one} from {c['make']} with {DRIVE_WORDS[c['drive']]}. "
            f"In short: {', '.join(traits)}.")


def _range_card(t: _Table, c: dict) -> str:
    text = (f"{_who(c)} range: {c['range_mi']} miles on a full charge ({t.level(c, 'range_mi', RANGE)}), "
            f"{t.ranked(c, 'range_mi', 'longest range', 'shortest range')}.")
    if c["range_city_mi"] is not None and c["range_hwy_mi"] is not None:
        text += f" About {c['range_city_mi']} miles in the city and {c['range_hwy_mi']} on the highway."
    return text


def _efficiency_card(t: _Table, c: dict) -> str:
    return (f"{_who(c)} efficiency: {c['mpge']} MPGe, using {_num(c['kwh_per_100mi'])} kWh of electricity "
            f"per 100 miles ({t.level(c, 'mpge', EFFICIENCY)}), "
            f"{t.ranked(c, 'mpge', 'most efficient', 'least efficient')}.")


def _cost_card(t: _Table, c: dict) -> str:
    return (f"{_who(c)} running cost: about ${c['annual_cost_usd']:,} a year for electricity, the EPA's estimate "
            f"for 15,000 miles ({t.level(c, 'annual_cost_usd', COST)}), "
            f"{t.ranked(c, 'annual_cost_usd', 'cheapest to run', 'most expensive to run', higher_is_top=False)}.")


def _charging_card(t: _Table, c: dict) -> str | None:
    if c["charge_240v_h"] is None:
        return None  # no figure: no card, rather than a made-up sentence
    return (f"{_who(c)} charging: about {_num(c['charge_240v_h'])} hours for a full charge on a 240-volt home "
            f"charger ({t.level(c, 'charge_240v_h', PACE, low_is_good=True)}), "
            f"{t.ranked(c, 'charge_240v_h', 'fastest to charge', 'slowest to charge', higher_is_top=False)}.")


def car_cards(cars: list[dict]) -> list[Card]:
    """Every card for every car, in table order. `cars` comes from collect/table.py."""
    t = _Table(cars)
    cards = []
    for c in cars:
        texts = {
            "overview": _overview_card(t, c),
            "range": _range_card(t, c),
            "efficiency": _efficiency_card(t, c),
            "cost": _cost_card(t, c),
            "charging": _charging_card(t, c),
        }
        stats = {s: c[s] for s in STATS}
        for facet, text in texts.items():
            if text is None:
                continue
            cards.append(Card(
                text=text, page_start=c["row"], page_end=c["row"],
                breadcrumb=f"{LIBRARY_LABEL} › {c['class']} › {c['name']} › {FACETS[facet]}",
                meta={"item": c["name"], "class": c["class"], "make": c["make"], "drive": c["drive"],
                      "facet": facet, "row": c["row"], "stats": stats},
            ))
    return cards
