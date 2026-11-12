"""
The rank stage (table libraries only): sort the candidates by the stat the
question asks for.

Search by meaning finds the right KIND of car ("pickup", "range"), but
vectors can't sort: the card that sounds most like "longest range" is not
the car with the longest range. So search returns more candidates than we
need (CANDIDATES cards, a wide net), and this stage:

  1. reads the intent from the question with plain rules: a stat (range,
     efficiency, running cost, charging time), a direction (best end or
     worst end) and, if named, a class (SUV, pickup...), a make (Tesla...)
     and a drive (AWD...). No AI call: cheap, testable, explainable;
  2. keeps the cards of that class, make and drive, and of the facet that
     holds the stat;
  3. groups them by car, sorts by the raw number in each card's meta, and
     returns the top 5 cars.

No stat word in the question ("a roomy car for a big family") means there is
nothing to sort by, so the order search gave is kept as it is.
"""

import re
from dataclasses import dataclass

# How many cards search hands to this stage. Measured on the golden set (docs/results.md):
# 20 -> recall@5 0.45, 50 -> 0.71, 100 -> 0.89, 200 -> 1.00. Questions about the best of ALL
# cars need a wide net: the winner's card may not sound the most like the question. 200 is
# about a sixth of the library's 1,155 cards, so this is still sorting a shortlist, not the table.
CANDIDATES = 200


@dataclass(frozen=True)
class Stat:
    words: str             # regex: the words that name this stat in a question
    worst: str             # regex: the words that ask for the bad end of THIS stat
    facet: str             # which card holds it
    column: str            # which number to sort by
    higher_is_better: bool
    label: str
    best_word: str         # how the good end is described
    worst_word: str
    unit: str


# Checked in this order: "cheapest to charge" is about cost, so cost is looked for before charging.
STATS: dict[str, Stat] = {
    "cost": Stat(r"\b(cheap(er|est)?|cost(s|ly|liest)?|running costs?|expensive|pricey|priciest|bills?|"
                 r"afford(able)?|save money|inexpensive)\b",
                 r"\b(most expensive|priciest|pricier|costliest|most costly|highest)\b|(?<!least )(?<!less )\bexpensive\b",
                 "cost", "annual_cost_usd", False, "running cost", "cheapest", "most expensive", "$ a year"),
    "charging": Stat(r"\b(charg(e|es|ed|ing)|recharg(e|es|ing)|240 ?v|level 2|plug(s|ged)? in)\b",
                     r"\b(slow(er|est)?|longest|most time)\b",
                     "charging", "charge_240v_h", False, "charging time", "fastest", "slowest", "hours"),
    "efficiency": Stat(r"\b(efficien(t|cy)|inefficient|mpge|kwh|economical|energy|electricity use|"
                       r"uses? (the )?(least|less|most) (energy|electricity|power))\b",
                       r"\b(least|less|lowest|worst) efficien|\binefficien|\buses? (the )?most\b|\blowest mpge\b",
                       "efficiency", "mpge", True, "efficiency", "most efficient", "least efficient", "MPGe"),
    "range": Stat(r"\b(range|miles|mileage|far(ther|thest)?|furthest|distance|road ?trips?|long (drives?|journeys?|trips?))\b",
                  r"\b(shortest|least|lowest|smallest|less)\b",
                  "range", "range_mi", True, "range", "longest", "shortest", "miles"),
}

# Words that ask for the bad end whatever the stat.
WORST = r"\b(worst|poorest)\b"

# What a question can call a kind of car, and which classes in the table that covers.
# Checked in this order, so "small SUV" is found before "SUV", and "minivan" before "van".
# Plain "SUV" means any SUV, small or not: that is what most people mean by it.
CLASSES: dict[str, tuple[str, frozenset]] = {
    "small SUV": (r"\b(small|compact|subcompact|mini|little) (electric )?(suvs?|crossovers?)\b", frozenset({"Small SUV"})),
    "large SUV": (r"\b(large|big|full-?size|standard|7-?seat(er)?|three-row) (electric )?(suvs?|crossovers?)\b", frozenset({"SUV"})),
    "SUV": (r"\b(suvs?|crossovers?)\b", frozenset({"Small SUV", "SUV"})),
    "pickup": (r"\b(pickups?|pick-ups?|trucks?)\b", frozenset({"Pickup"})),
    "small car": (r"\b(small|compact|subcompact|city|little|tiny) (electric )?(cars?|evs?|hatch(back)?s?|sedans?)\b",
                  frozenset({"Small car"})),
    "midsize car": (r"\b(mid-?size|midsized|medium) (electric )?(cars?|evs?|sedans?)\b", frozenset({"Midsize car"})),
    "large car": (r"\b(large|full-?size|big) (electric )?(cars?|evs?|sedans?|saloons?)\b", frozenset({"Large car"})),
    "sedan": (r"\b(sedans?|saloons?)\b", frozenset({"Small car", "Midsize car", "Large car"})),
    "wagon": (r"\b(wagons?|estates?)\b", frozenset({"Wagon"})),
    "minivan": (r"\b(minivans?|mpvs?|people carriers?)\b", frozenset({"Minivan"})),
    "two-seater": (r"\b(two-?seaters?|roadsters?|sports cars?)\b", frozenset({"Two-seater"})),
    "van": (r"\b(vans?)\b", frozenset({"Van"})),
}

DRIVES = {
    "AWD": r"\b(awd|all-?wheel( drive)?|4wd|4x4|four-?wheel( drive)?)\b",
    "RWD": r"\b(rwd|rear-?wheel( drive)?)\b",
    "FWD": r"\b(fwd|front-?wheel( drive)?)\b",
}

# What people call a make, when it isn't the make's own name.
MAKE_ALIASES = {"chevy": "Chevrolet", "vw": "Volkswagen", "merc": "Mercedes-Benz", "mercedes": "Mercedes-Benz",
                "benz": "Mercedes-Benz", "bugatti": "Bugatti Rimac", "rimac": "Bugatti Rimac", "rolls": "Rolls-Royce"}


@dataclass(frozen=True)
class Intent:
    stat: str | None = None        # a key of STATS, or None: nothing to sort by
    best_end: bool = True          # False = the question asks for the bad end (shortest, most expensive...)
    item_class: str | None = None  # a key of CLASSES, e.g. "SUV" (which covers small SUVs too)
    make: str | None = None        # as the table spells it, e.g. "Mercedes-Benz"
    drive: str | None = None       # AWD | FWD | RWD

    @property
    def facet(self) -> str | None:
        return STATS[self.stat].facet if self.stat else None

    @property
    def column(self) -> str | None:
        return STATS[self.stat].column if self.stat else None

    @property
    def descending(self) -> bool:
        """Sort big-to-small? Yes when asking for the best of a higher-is-better stat, or the worst of a lower-is-better one."""
        return STATS[self.stat].higher_is_better == self.best_end

    def understood(self) -> str:
        """What the walk and the Journey show: "SUV · range · longest"."""
        if self.stat is None:
            return "no stat to sort by"
        s = STATS[self.stat]
        parts = [p for p in (self.make, self.drive, self.item_class) if p]
        parts += [s.label, s.best_word if self.best_end else s.worst_word]
        return " · ".join(parts)


# Makes that are also everyday words ("a mini SUV"): found only as written here, case and all.
WORD_MAKES = {"MINI": r"\b(MINI|Mini Cooper|Mini Countryman|Countryman)\b"}


def find_make(question: str, makes) -> str | None:
    """The make the question names, if any: "tesla", "mercedes", "chevy"."""
    q = question.lower()
    for make in sorted(makes, key=len, reverse=True):  # "Mercedes-Benz" before a shorter make inside it
        if make in WORD_MAKES:
            if re.search(WORD_MAKES[make], question):
                return make
            continue
        names = {make.lower(), make.lower().split("-")[0], make.lower().split()[0]}
        if any(re.search(rf"\b{re.escape(n)}\b", q) for n in names):
            return make
    for alias, make in MAKE_ALIASES.items():
        if make in makes and re.search(rf"\b{alias}\b", q):
            return make
    return None


# "How far on a charge" is about range, not about charging: say so before the charging words are looked for.
ON_A_CHARGE = r"\b(on|per|from) (a|one) (single |full )?charge\b"


def parse_intent(question: str, makes=()) -> Intent:
    q = question.lower()
    q_stats = re.sub(ON_A_CHARGE, " range ", q)
    stat = next((name for name, s in STATS.items() if re.search(s.words, q_stats)), None)
    worst = bool(stat) and bool(re.search(STATS[stat].worst, q) or re.search(WORST, q))
    cls = next((name for name, (pattern, _) in CLASSES.items() if re.search(pattern, q)), None)
    drive = next((name for name, pattern in DRIVES.items() if re.search(pattern, q)), None)
    return Intent(stat=stat, best_end=not worst, item_class=cls, make=find_make(question, makes), drive=drive)


def rank(question: str, hits: list[dict], top: int = 5) -> tuple[list[dict], dict]:
    """hits: the candidates from search, best match first, each with a "meta" dict.

    Returns (the hits to keep, in their new order; a report for the trace).
    When the question names no stat this is a no-op: the first `top` hits, as search ordered them."""
    pool = [h for h in hits if h.get("meta")]
    intent = parse_intent(question, makes={h["meta"].get("make") for h in pool} - {None})
    report = {"understood": intent.understood(), "applied": False, "candidates": len(hits),
              "stat": intent.stat, "item_class": intent.item_class, "make": intent.make, "drive": intent.drive,
              "direction": None, "column": intent.column, "items": [],
              # What search handed over, in its own order, so the trace can show the "before".
              "before": [{"chunk_id": h["chunk_id"], "item": h["meta"]["item"], "facet": h["meta"]["facet"],
                          "score": h["score"]} for h in pool]}
    if intent.stat is None:
        return hits[:top], report

    s = STATS[intent.stat]
    report["direction"] = s.best_word if intent.best_end else s.worst_word
    # Keep what was asked for: the class, the make, the drive, then the facet that holds the stat.
    # If search returned none of them, fall back to what it did return instead of answering nothing.
    classes = CLASSES[intent.item_class][1] if intent.item_class else None
    for wanted, keep in ((classes, lambda h: h["meta"]["class"] in classes),
                         (intent.make, lambda h: h["meta"].get("make") == intent.make),
                         (intent.drive, lambda h: h["meta"].get("drive") == intent.drive),
                         (intent.facet, lambda h: h["meta"]["facet"] == intent.facet)):
        if wanted:
            pool = [h for h in pool if keep(h)] or pool

    # One card per car (its best-matching one), and only cars that have the number.
    by_item: dict[str, dict] = {}
    for h in pool:
        if h["meta"]["stats"].get(intent.column) is not None:
            by_item.setdefault(h["meta"]["item"], h)
    if not by_item:
        return hits[:top], report

    def key(h: dict):
        value = h["meta"]["stats"][intent.column]
        # Ties: the card that matched the question better comes first, then the name, so the order never wobbles.
        return (-value if intent.descending else value, -h["score"], h["meta"]["item"])

    kept = sorted(by_item.values(), key=key)[:top]
    report.update(applied=True, items=[
        {"item": h["meta"]["item"], "value": h["meta"]["stats"][intent.column], "unit": s.unit,
         "chunk_id": h["chunk_id"]} for h in kept])
    return kept, report
