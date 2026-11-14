# Development

[← Back to the README](../README.md)

## How it fits together

```
EPA download ─▶ build_ev_table.py ─▶ vehicles.csv (committed)
vehicles.csv ─▶ check + register (sha256) ─▶ cards (one per car and facet, numbers as words)
            ─▶ embed (bge-small, 384 dims) ─▶ Postgres + pgvector
question ─▶ embed ─▶ search (exact or HNSW, 200 candidates) ─▶ rank (sort by the stat asked for)
         ─▶ assemble ─▶ Claude Haiku ─▶ citation check ─▶ trace
                                                      golden set ─▶ recall@5, MRR
```

| Folder | What's there |
| --- | --- |
| `backend/pipeline/` | collect, parse, chunk, evaluate, answer. `python -m pipeline --help` |
| `backend/app/` | FastAPI: `/api/libraries`, `/api/stars`, `/api/examples`, `/api/ask`, `/api/health`; rate limits (`guard.py`), replays (`baked.py`) |
| `frontend/` | The three films (React + React Three Fiber). `src/Site.jsx` picks the film from the address and fades between them. Main film: `src/App.jsx`, with `src/story.js` (every chapter's words), `src/timeline.js` (the one number that drives a film), `src/layout.js` (where things are and where the camera stands), `src/scene/` (the 3D picture) and `src/ui/` (the words on top). Search film: `src/hnsw/` (`graph.js` the toy graph and the walk, `story.js` the words, `Scene.jsx` the picture). Journey: `src/journey/` (`stops.js` the words and code references, `Look.jsx` what the question looks like at each stop, `Track.jsx` the picture). `code-lines.js` finds each referenced function's line when the site is built, and `saved-example.js` copies the first saved example in for the journey |
| `scripts/` | `dev.sh` / `dev.ps1` (run everything), `build_ev_table.py` (EPA download -> `vehicles.csv`) |
| `infra/` | Terraform for Azure: database, API, site, secrets, budget alert. `infra/README.md` has the steps |
| `.github/workflows/` | `api-image.yml` builds the API's container image and puts it on GitHub's registry; `site.yml` builds the site and publishes it to Azure |
| `data/seeds/ev/` | the electric car table (`vehicles.csv`) and where it comes from (`SOURCE.md`) |
| `docs/` | results, glossary |

## Run it locally

Needs Docker Desktop, Python 3.11+, Node 20+.

```bash
./scripts/dev.sh        # macOS / Linux: Postgres in Docker, tables, API on :8000, app on :5173
.\scripts\dev.ps1       # Windows (PowerShell): the same steps
```

On Windows, install them with `winget install Python.Python.3.12 Docker.DockerDesktop OpenJS.NodeJS.LTS`,
then open a new terminal so `python` and `docker` are found.

Then fill the database (in another terminal, from `backend/` with `source .venv/bin/activate`,
or `.venv\Scripts\Activate.ps1` on Windows). The library is a table, so there is no collect or parse
step, and its run is always `cards/0`:

```bash
python -m pipeline register      # checks data/seeds/ev/vehicles.csv, registers it by fingerprint
python -m pipeline chunk         # 231 cars -> 1,155 cards, embedded, raw numbers kept in chunks.meta
python -m pipeline hnsw
python -m pipeline eval          # "cards" (search alone) vs "cards + rank", scored on car names
python -m pipeline bake          # pre-compute the home-page examples (needs ANTHROPIC_API_KEY); commit backend/app/baked/ev.json
python -m pipeline ask "longest range electric SUV"
```

To refresh the table from the EPA: download https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip,
unzip it, run `python scripts/build_ev_table.py path/to/vehicles.csv`, then `register` and `chunk` again.

The PDF pipeline (`register` for an inbox of PDFs, `parse`, the `fixed` and `structure`
chunkers) is still in the code, unused by the current library.

Restart the API after chunking or baking so it loads the new stars and examples.
Tests: `cd backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest`
(on Windows: `.venv\Scripts\python -m pytest`).

## Running it in public

The live demo calls Claude for every new question, so it is protected:

- **Example questions are pre-computed.** `python -m pipeline bake` runs each one once and saves the
  full trace to `backend/app/baked/<library>.json` (committed, so it ships in the Docker image). The site
  replays them instantly with no AI call and labels them "Instant replay". If the chunks are rebuilt,
  stale replays are ignored at startup until you bake again.
- **Repeated questions** are served from memory (the last 256).
- **New questions are rate limited** per visitor (`RATE_PER_MINUTE`, `RATE_PER_DAY`) with a site-wide
  daily cap on AI calls (`DAILY_AI_BUDGET`). The per-day counts are kept in the database (`limits` table),
  because the live server sleeps when idle and starts afresh: counts held only in memory would reset
  several times a day. A visitor is stored as a one-day fingerprint of their address, never the address.
- **Every request is guarded** (`backend/app/shield.py`): a message may be at most 8 KB, one visitor may
  make at most `REQUESTS_PER_MINUTE` requests of any kind, and FastAPI's documentation pages are off.
- **The browser is told to be strict**: the site sends a content security policy
  (`frontend/public/staticwebapp.config.json`, which names the API's address: change it there if the
  API moves), and neither the site nor the API may be shown inside another page.
- **Set a spending limit in the Anthropic console too.** The caps above are the first line of defence;
  that limit is the backstop if they are ever wrong.
- **Claude failures** (rate limits, timeouts, outages) are shown in the trace; the visitor still sees the retrieval.

Building the frontend for production: set `VITE_API_URL` (the API's address) and `VITE_SITE_URL`
(the site's address, for link previews) as in `frontend/.env.example`, then `npm run build`.
Set `VITE_COMMIT` to the commit being deployed, so the journey's links open the code that is actually running
(without it they point at `main`). The build stops if `src/journey/stops.js` names a function that no longer exists.
The API needs `CORS_ORIGINS` set to the site's address, and `TRUSTED_PROXIES=1` when it runs behind
one proxy of your own (Azure Container Apps), so the rate limiter counts the real visitor (`guard.visitor_id`).

Moving through the film: scroll, swipe, the arrow keys, or the arrows on screen. `Esc` returns to the
title. A step of one or two chapters is travelled; a longer jump (such as "Ask another" at the end) is a cut:
the frame dips to black and comes back on the new chapter, rather than playing everything in between at speed. On the map chapters, point at a dot to read its passage and drag to turn the view.
While developing, the film's clock is reachable from the browser console: `__tl.target = 4.5` holds it
halfway between chapters 4 and 5 (`__hnsw` and `__journey` are the clocks of the two smaller films).

The two smaller films open from the start page ("How search stays fast", "The question's journey"), from a
quiet link under chapter 6 ("What if there were millions?") and chapter 8 ("The same trip, told by the
question"), or directly at `/#hnsw` and `/#journey`. They move the same way, and
`Esc` or the name top left returns to the main film, exactly where it was left. With no question asked yet,
the journey follows the first saved example, which is copied into the site when it is built
(`frontend/saved-example.js`), so it appears at once even while the server is asleep.

## Data source and terms

US EPA and US Department of Energy fuel economy data (fueleconomy.gov), 2026 model year. EPA data is in
the public domain (https://edg.epa.gov/EPA_Data_License.htm; 17 U.S.C. § 105). The figures are
standardised test estimates for comparing cars; real range and costs vary. Details, columns and what the
data can't answer: `data/seeds/ev/SOURCE.md`.

