"""
Build data/seeds/ev/vehicles.csv from the EPA's fuel economy download.

    curl -LO https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip && unzip vehicles.csv.zip
    python scripts/build_ev_table.py path/to/vehicles.csv

What it keeps: battery-electric vehicles (atvType = EV) of one model year.
The EPA lists every wheel and tyre option as its own row ("R1S Dual Max (22in)",
"(21 inch Wheels)"), so those words are stripped from the name and each
make + model is kept once: the version with the longest range.

The output is committed, so the app never needs the 40 MB download. Re-run
this to refresh it, then `python -m pipeline register` and `chunk`.
"""

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "seeds" / "ev" / "vehicles.csv"
YEAR = "2026"

# EPA size class -> the class a person would say
CLASSES = [
    (r"^Small Sport Utility", "Small SUV"),
    (r"^Standard Sport Utility", "SUV"),
    (r"Pickup", "Pickup"),
    (r"^(Minicompact|Subcompact|Compact) Cars", "Small car"),
    (r"^Midsize Cars", "Midsize car"),
    (r"^Large Cars", "Large car"),
    (r"Station Wagons", "Wagon"),
    (r"^Minivan", "Minivan"),
    (r"^Two Seaters", "Two-seater"),
    (r"^Special Purpose", "Van"),
]
DRIVES = {"All-Wheel Drive": "AWD", "4-Wheel Drive": "AWD", "Part-time 4-Wheel Drive": "AWD",
          "Front-Wheel Drive": "FWD", "Rear-Wheel Drive": "RWD"}

# Wheel, tyre and charger options: the same car, so they are not part of its name.
OPTION = re.compile(r"""
    \s*\([^)]*(\binch\b|\d\s*in\b|\d"|wheel|tire|tyre|charger|\b\d+R\b)[^)]*\)   # (22in), (21 inch Wheels), (11kW Charger), (2R)
  | \s+w/.*$                                                                   # w/21in All-Season Tires
  | \s+with\s*\d+.*$                                                            # with 20 inch wheels, with19 inch wheels
  | \s+(\S+\s+)?wheels?\b.*$                                                    # Aero-Design wheel (285/35)
  | \s+\d{2}\s*(-?inch|in)\b(\s+wheels?)?                                      # 20 inch, 22in
  | \s*\(R\d+\)                                                                  # (R22): a wheel size
  | \s+\d+\s*kW\s+charger\b                                                       # 11 kW Charger: an option
  | \s+\d{3}/\d{2}Z?R\d{2}.*$                                                       # 305/35ZR20: a tyre size
  | \s+tires?$
  | \s+All[- ]Season(\s+Tires?)?(\s*\(M\+S\))?$                                  # All-Season (M+S)
""", re.I | re.X)

COLUMNS = ["name", "make", "model", "year", "class", "drive", "range_mi", "range_city_mi", "range_hwy_mi",
           "mpge", "kwh_per_100mi", "charge_240v_h", "annual_cost_usd", "epa_id"]


def clean_model(model: str) -> str:
    prev = None
    while prev != model:
        prev, model = model, OPTION.sub("", model).strip(" -,")
    return re.sub(r"\s{2,}", " ", model)


def class_of(vclass: str) -> str:
    for pattern, name in CLASSES:
        if re.search(pattern, vclass):
            return name
    raise ValueError(f"unknown EPA class {vclass!r}")


def num(x: str):
    try:
        v = float(x)
    except ValueError:
        return None
    return v if v > 0 else None


def build(src: Path) -> list[dict]:
    best: dict[tuple, dict] = {}
    for r in csv.DictReader(src.open(encoding="utf-8", errors="replace")):
        if r["atvType"] != "EV" or r["year"] != YEAR or not num(r["range"]):
            continue
        model = clean_model(r["model"])
        row = {
            "name": f"{r['make']} {model}", "make": r["make"], "model": model, "year": int(r["year"]),
            "class": class_of(r["VClass"]), "drive": DRIVES.get(r["drive"], r["drive"]),
            "range_mi": int(float(r["range"])),
            "range_city_mi": round(num(r["rangeCity"])) if num(r["rangeCity"]) else "",
            "range_hwy_mi": round(num(r["rangeHwy"])) if num(r["rangeHwy"]) else "",
            "mpge": int(float(r["comb08"])),
            "kwh_per_100mi": round(float(r["combE"]), 1),
            "charge_240v_h": round(num(r["charge240"]), 1) if num(r["charge240"]) else "",
            "annual_cost_usd": int(float(r["fuelCost08"])),
            "epa_id": int(r["id"]),
        }
        key = (row["make"].lower(), row["model"].lower())
        if key not in best or row["range_mi"] > best[key]["range_mi"]:
            best[key] = row
    return sorted(best.values(), key=lambda r: (r["make"].lower(), r["model"].lower()))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("epa_csv", type=Path)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    rows = build(a.epa_csv)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")  # LF, as git stores it
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} vehicles ({YEAR}) -> {a.out}")
    print(Counter(r["class"] for r in rows).most_common())


if __name__ == "__main__":
    main()
