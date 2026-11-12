"""
The libraries: separate collections of passages, searched one at a time.

Every row in the pipeline (manifest, chunks, traces) records which library it
belongs to, and every search is filtered to one library. The filter happens
inside the search (each library has its own HNSW index), not afterwards, so
asking "find the 5 closest" really returns 5 from the chosen library.

There is one library today:

  ev   electric cars: the US EPA's range, efficiency, running-cost and
       charging figures for every 2026 battery-electric model. Numbers, not
       prose, so each row is turned into word "cards" (chunk/cards.py) and
       answers are sorted by a rank stage (answer/rank.py).

The PDF pipeline (register, parse, the fixed and structure chunkers) still
works for a library of documents: add one here with an "inbox" folder.
"""

from .config import DATA

LIBRARIES: dict[str, dict] = {
    "ev": {
        "title": "Electric cars",
        "short": "EVs",       # the one word the site uses for it
        "description": "Every 2026 electric car the US EPA has tested: range, efficiency, running cost and charging time.",
        "table": DATA / "seeds" / "ev" / "vehicles.csv",  # the whole library is this one CSV
        "run": ("cards", 0),   # a table has one way to be chunked, so its run is fixed (size isn't used)
        "rank": True,          # sort the candidates by the stat the question asks for
        "examples": [
            "longest range electric SUV",
            "most efficient small car",
            "cheapest electric pickup to run",
            "a small electric car for city driving",
        ],
        "credit": "Data: US EPA and US Department of Energy, fueleconomy.gov (2026 model year, downloaded 2026-11-12). "
                  "Public domain. Estimates for comparison only; real-world range and costs vary.",
    },
}

ORDER = ["ev"]  # the order the site offers them in; the first with passages opens by default
DEFAULT_CLI_LIBRARY = "ev"  # pipeline commands without --library act on this one


def check(library: str) -> str:
    if library not in LIBRARIES:
        raise ValueError(f"Unknown library {library!r}. Choose one of: {', '.join(ORDER)}")
    return library


def is_table(library: str) -> bool:
    return "table" in LIBRARIES[check(library)]


def run_of(library: str, chunker: str, size: int) -> tuple[str, int]:
    """Which (chunker, size) to use: the library's own fixed run if it has one, otherwise what was asked for."""
    return LIBRARIES[check(library)].get("run") or (chunker, size)
