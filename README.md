<div align="center">

# RAG Galaxy

**Follow a question through a real RAG pipeline, in 3D.**

[Live demo](https://kind-glacier-05a1dd40f.3.azurestaticapps.net) · [The films](docs/films.md) · [Results](docs/results.md) · [Development](docs/development.md)

<br>

<img src="docs/images/search-film.jpg" width="720" alt="The search film: a point of light walks a graph of passages towards the question">

</div>

<br>

Ask about 231 electric cars (US EPA, 2026 models) and watch the question become a vector, find its nearest passages, and come back as an answer with citations you can check.

```
question
  → embed     bge-small · 384 dims
  → search    pgvector · HNSW
  → rank      by the stat you asked for
  → answer    Claude Haiku
  → check     every citation verified
```

| | Golden set (20 questions) |
| --- | --- |
| Search alone | recall@5 0.31 |
| Search + rank | 20 / 20 found |

**Stack** · Python · FastAPI · Postgres + pgvector · React Three Fiber · Claude · Terraform · Azure

## Run it

```bash
./scripts/dev.sh
```

Needs Docker, Python 3.11+ and Node 20+. Filling the database, tests and deployment: [docs/development.md](docs/development.md).

<sub>Code: MIT · Data: US EPA, public domain</sub>
