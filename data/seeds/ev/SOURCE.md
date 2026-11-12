# Electric cars: where `vehicles.csv` comes from

**Short answer: the US EPA's fuel economy data, the 2026 model year, battery-electric cars only.**
231 cars from 30 makes, downloaded on 2026-11-12.

| | |
|---|---|
| Publisher | US Environmental Protection Agency (EPA) and US Department of Energy, via fueleconomy.gov |
| Download | https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip (documentation: https://www.fueleconomy.gov/feg/ws/index.shtml#vehicle) |
| Catalogue entry | https://catalog.data.gov/dataset/www-fueleconomy-gov (access level: public) |
| Licence | https://edg.epa.gov/EPA_Data_License.htm: EPA data is "by default in the public domain" and "not subject to domestic copyright protection under 17 U.S.C. § 105". No attribution required; we credit the source anyway. |

## How the table was made

`scripts/build_ev_table.py` turns the 40 MB download (every car since 1984) into this file:

1. Keep rows with `atvType = EV` (battery-electric) and `year = 2026`.
2. The EPA lists each wheel, tyre and charger option as its own row ("R1S Dual Max (22in)",
   "(21 inch Wheels)", "11 kW Charger"). Those words are stripped from the name, and each make + model
   is kept once: the version with the longest range. 335 rows become 231 cars.
3. The EPA's size class is turned into a word a person would use (`Small Sport Utility Vehicle 4WD`
   becomes `Small SUV`), and the drive into AWD, FWD or RWD.

Re-run it to refresh the table, then `python -m pipeline register` and `python -m pipeline chunk`.

## The columns

| Column | EPA field | Meaning |
|---|---|---|
| `range_mi` | `range` | Miles on a full charge, combined city and highway |
| `range_city_mi`, `range_hwy_mi` | `rangeCity`, `rangeHwy` | The same, city only and highway only |
| `mpge` | `comb08` | Miles per gallon-equivalent, combined: how far the car goes on the energy in a gallon of petrol (33.7 kWh) |
| `kwh_per_100mi` | `combE` | Electricity used per 100 miles. The same measurement as MPGe, the other way up; the loader checks they agree |
| `charge_240v_h` | `charge240` | Hours for a full charge on a 240-volt home charger |
| `annual_cost_usd` | `fuelCost08` | The EPA's estimate of a year's electricity, for 15,000 miles (55% city) at the EPA's assumed price |
| `epa_id` | `id` | The EPA's row id, so any figure can be checked at fueleconomy.gov |

## What the table can't answer

Purchase prices, safety ratings, top speed, acceleration, seats and boot space are not in the EPA's data.
Questions about them should get "the sources don't say", and two golden questions check that.

The figures are standardised test results, for comparing cars with each other. Real range and costs vary
with weather, speed, driving style and electricity prices.

## Some EPA classes are surprising

The EPA classes cars by interior volume, not by how they are marketed. The 2026 Nissan LEAF and the
Mercedes-Benz EQE SUV are "station wagons", for example. The table keeps the EPA's class, so a question
about wagons gets the EPA's answer.
