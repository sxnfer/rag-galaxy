"""
Collect for a library that is a table, not a pile of PDFs (the electric cars).

The whole library is one CSV, committed under data/seeds/ (built from the
EPA's download by scripts/build_ev_table.py). Two jobs here:

  1. load():  read it and check it. A bad cell stops the run with the row
     number, so a typo is found here and not three steps later in an answer.
  2. run():   register it like a PDF. Its sha256 fingerprint goes in the
     manifest (doc_type = stat_sheet), so running this twice adds nothing,
     and an edited CSV becomes a new document.

Row numbers are the ones a spreadsheet shows: the header is row 1, the first
car is row 2. They become the "page" a citation points at.
"""

import csv
import io
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..config import FILES_DIR
from ..libraries import LIBRARIES, check

DOC_TYPE = "stat_sheet"
CLASSES = ("Small car", "Midsize car", "Large car", "Small SUV", "SUV", "Pickup", "Wagon", "Minivan", "Two-seater", "Van")
DRIVES = ("AWD", "FWD", "RWD")

# column: (lowest allowed, highest allowed, may be left blank, whole number)
NUMERIC: dict[str, tuple[float, float, bool, bool]] = {
    "year":            (2010, 2035, False, True),
    "range_mi":        (30, 1000, False, True),     # miles on a full charge, EPA combined
    "range_city_mi":   (30, 1000, True, True),
    "range_hwy_mi":    (30, 1000, True, True),
    "mpge":            (20, 250, False, True),      # miles per gallon-equivalent, combined
    "kwh_per_100mi":   (10, 100, False, False),     # electricity used per 100 miles
    "charge_240v_h":   (1, 48, True, False),        # hours to charge on a 240 V home charger
    "annual_cost_usd": (100, 5000, False, True),    # EPA's yearly electricity cost estimate
    "epa_id":          (1, 10_000_000, False, True),
}
TEXT = ("name", "make", "model", "class", "drive")
COLUMNS = (*TEXT, *NUMERIC)


class TableError(ValueError):
    """Something in the CSV is wrong. The message says which row."""


def parse_table(text: str) -> list[dict]:
    """CSV text -> one dict per car, numbers as numbers, blanks as None, plus "row"."""
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise TableError(f"row 1 (the header): missing column(s) {', '.join(missing)}")
    cars, seen = [], {}
    for row_no, raw in enumerate(reader, start=2):
        where = f"row {row_no}"
        name = (raw["name"] or "").strip()
        if not name:
            raise TableError(f"{where}: name is empty")
        where = f"row {row_no} ({name})"
        if name.lower() in seen:
            raise TableError(f"{where}: the name is already used in row {seen[name.lower()]}")
        seen[name.lower()] = row_no
        car = {"row": row_no, **{c: (raw[c] or "").strip() for c in TEXT}}
        if car["class"] not in CLASSES:
            raise TableError(f"{where}: class {car['class']!r} is not one of {', '.join(CLASSES)}")
        if car["drive"] not in DRIVES:
            raise TableError(f"{where}: drive {car['drive']!r} is not one of {', '.join(DRIVES)}")
        for col, (low, high, blank_ok, whole) in NUMERIC.items():
            cell = (raw[col] or "").strip()
            if not cell:
                if not blank_ok:
                    raise TableError(f"{where}: {col} is empty")
                car[col] = None
                continue
            try:
                value = float(cell)
            except ValueError:
                raise TableError(f"{where}: {col} is {cell!r}, not a number") from None
            if not low <= value <= high:
                raise TableError(f"{where}: {col} is {cell}, outside {low:g} to {high:g}")
            if whole and value != int(value):
                raise TableError(f"{where}: {col} is {cell}, but it must be a whole number")
            car[col] = int(value) if whole else value
        # MPGe and kWh per 100 miles are the same measurement two ways (33.7 kWh = 1 gallon of petrol),
        # so a row where they disagree has a typo in one of them.
        implied = 3370 / car["kwh_per_100mi"]
        if abs(implied - car["mpge"]) > 0.05 * car["mpge"] + 1:
            raise TableError(f"{where}: mpge {car['mpge']} doesn't match kwh_per_100mi {car['kwh_per_100mi']} "
                             f"(that would be about {implied:.0f} MPGe)")
        cars.append(car)
    if not cars:
        raise TableError("the table has a header but no rows")
    return cars


def load(path: Path) -> list[dict]:
    try:
        return parse_table(Path(path).read_text(encoding="utf-8"))
    except TableError as e:
        raise TableError(f"{Path(path).name}, {e}") from None


def latest(conn, library: str) -> tuple[str, str] | None:
    """(sha256, local_path) of the newest registered stat sheet for this library."""
    return conn.execute(
        """select sha256, local_path from manifest
           where library = %s and doc_type = %s and sha256 is not null
           order by fetched_at desc limit 1""", (library, DOC_TYPE)).fetchone()


def run(library: str) -> dict:
    from ..db import connect               # imported here so load() works without a database
    from .register import sha256_of

    meta = LIBRARIES[check(library)]
    source: Path = meta["table"]
    cars = load(source)                    # refuse to register a table that doesn't pass the checks
    digest = sha256_of(source)
    with connect() as conn:
        if conn.execute("select 1 from manifest where sha256 = %s", (digest,)).fetchone():
            print(f"Done ({library}): 0 new, 1 already registered ({source.name} {digest[:12]})")
            return {"new": 0, "already": 1}
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        target = FILES_DIR / f"{digest}.csv"
        shutil.copy2(source, target)
        # The fingerprint is part of the address, so an edited CSV is a new document
        # and the old one stays on record.
        conn.execute(
            """insert into manifest (library, project_id, project_title, doc_type, link_text, source_url,
                                     sha256, local_path, fetched_at)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (library, library, meta["title"], DOC_TYPE, source.name,
             f"seed://{library}/{source.name}#{digest[:12]}", digest, str(target), datetime.now(timezone.utc)))
        conn.commit()
    print(f"  registered {source.name} ({DOC_TYPE}, {len(cars)} rows) {digest[:12]}")
    print(f"Done ({library}): 1 new, 0 already registered")
    return {"new": 1, "already": 0}
