"""
RAG Galaxy API.

The pipeline (backend/pipeline) does the heavy lifting offline: collect,
parse, chunk, embed. This server answers questions live over what it stored,
and returns a trace of every stage for the browser to replay.

Libraries: the site offers more than one collection of documents (see
pipeline/libraries.py). Each request says which library to use; search only
ever looks inside that one.

Which chunks it searches in a library is the "active run": RUN_CHUNKER +
RUN_SIZE in .env (default: fixed, 300 words), always with the embedder's own model.
A table library (the electric cars) has one fixed run, cards/0, whatever .env says.

Public-demo protection (see guard.py and baked.py):
  - the example questions are replayed from saved traces, with no AI call;
  - a repeated question is served from memory;
  - everything else is rate limited per visitor, with a daily cap on AI calls.
    The limits are shared across libraries: switching library doesn't reset them.
  - every request of any kind is size-limited and rate limited (shield.py), and the
    developer pages FastAPI normally serves (/docs, /openapi.json) are switched off.
"""

import os
import time
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pipeline.answer.pipeline import answer
from pipeline.db import as_np, connect
from pipeline.libraries import LIBRARIES, ORDER, run_of

from . import baked
from .embedder import load_embedder
from .galaxy import Galaxy
from .guard import AnswerCache, Guard, Ledger, Limited, visitor_id
from .shield import BodyLimit, RequestRate, SecurityHeaders

MAX_QUESTION_CHARS = 300
MAX_LIBRARY_CHARS = 40  # a library id is one short word; anything longer is not worth reading

state: dict = {}


def active_run(library: str, model: str) -> tuple[str, str, int, str]:
    chunker, size = run_of(library, os.environ.get("RUN_CHUNKER", "fixed"), int(os.environ.get("RUN_SIZE", "300")))
    return (library, chunker, size, model)


def load_galaxy(run) -> Galaxy:
    with connect() as conn:
        rows = conn.execute(
            """select c.id, c.embedding, c.breadcrumb, m.doc_type, m.project_id, c.page_start, c.page_end, c.doc_sha256,
                      c.meta
               from chunks c join manifest m on m.sha256 = c.doc_sha256
               where c.library=%s and c.chunker=%s and c.chunk_size=%s and c.model=%s order by c.id""", run).fetchall()
    return Galaxy([(r[0], as_np(r[1]), *r[2:]) for r in rows])


def load_library(library: str, embedder) -> dict:
    run = active_run(library, embedder.name)
    galaxy = load_galaxy(run)
    return {"run": run, "galaxy": galaxy, "baked": baked.load(run, galaxy)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = time.perf_counter()
    state["embedder"] = load_embedder()
    state["libraries"] = {lib: load_library(lib, state["embedder"]) for lib in ORDER}
    state["guard"] = Guard(ledger=Ledger(connect))  # shared by every library; per-day counts are kept in the database
    state["cache"] = AnswerCache()
    for lib, s in state["libraries"].items():
        print(f"[{lib}] {len(s['galaxy'].rows)} chunks for run {s['run'][1:3]}")
    print(f"Ready in {(time.perf_counter() - t) * 1000:.0f} ms")
    yield


# The public server has no use for FastAPI's built-in documentation pages, so they are switched off:
# they would only tell a stranger what to try.
app = FastAPI(title="RAG Galaxy", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
# Middleware is wrapped around the app like layers of an onion, and the LAST one added is the
# outermost: a request meets CORS first, then the three guards in shield.py, then compression.
app.add_middleware(GZipMiddleware, minimum_size=1024)  # the passage map is 240 KB of text: send it compressed
app.add_middleware(BodyLimit)
app.add_middleware(RequestRate)
app.add_middleware(SecurityHeaders)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def library_state(library: str) -> dict:
    if library not in LIBRARIES:
        raise HTTPException(400, f"Unknown library {library!r}. Choose one of: {', '.join(ORDER)}")
    return state["libraries"][library]


class AskRequest(BaseModel):
    question: str = Field(max_length=MAX_QUESTION_CHARS)
    library: str = Field(ORDER[0], max_length=MAX_LIBRARY_CHARS)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "libraries": {lib: len(s["galaxy"].rows) for lib, s in state["libraries"].items()}}


@app.get("/api/libraries")
def libraries() -> dict:
    """Every library the site offers, in order, with plain-English descriptions and sizes.
    "default" is the first library that has passages."""
    out = []
    for lib in ORDER:
        s, meta = state["libraries"][lib], LIBRARIES[lib]
        rows = s["galaxy"].rows
        out.append({
            "id": lib, "title": meta["title"], "short": meta["short"], "description": meta["description"], "credit": meta["credit"],
            "passages": len(rows), "documents": len({r[7] for r in rows}),
            "projects": len({r[4] for r in rows}), "ready": bool(rows),
        })
    default = next((x["id"] for x in out if x["ready"]), ORDER[0])
    return {"libraries": out, "default": default}


@app.get("/api/stars")
def stars(library: str = Query(ORDER[0], max_length=MAX_LIBRARY_CHARS)) -> dict:
    s = library_state(library)
    return {"library": library, "model": state["embedder"].name, "run": s["run"][1:3], "stars": s["galaxy"].stars()}


@app.get("/api/examples")
def examples(library: str = Query(ORDER[0], max_length=MAX_LIBRARY_CHARS)) -> dict:
    """The home-page questions for one library. "ready" ones replay instantly with no AI call."""
    return {"library": library, "examples": baked.examples(library, library_state(library)["baked"])}


@app.post("/api/ask")
def ask(req: AskRequest, request: Request):
    q = req.question.strip()
    if not q:
        raise HTTPException(400, "Empty question")
    lib = library_state(req.library)
    if not lib["galaxy"].rows:
        raise HTTPException(503, f"The {LIBRARIES[req.library]['title']} library is empty right now.")

    # 1. An example question: replay the saved trace. Free, instant, unlimited.
    replayed = baked.replay(lib["baked"], q, lib["galaxy"])
    if replayed:
        return replayed

    # 2. Asked recently by anyone, in the same library: serve it again from memory. Also free.
    cache_key = f"{req.library}::{q}"
    cached = state["cache"].get(cache_key)
    if cached:
        return {**cached, "cached": True}

    # 3. A new question: this one costs, so it is rate limited.
    visitor = visitor_id(request.client.host if request.client else None, request.headers.get("x-forwarded-for"))
    try:
        state["guard"].check(visitor)
    except Limited as e:
        return JSONResponse({"detail": str(e), "retry_after": e.retry_after}, status_code=429,
                            headers={"Retry-After": str(e.retry_after)})

    trace = answer(q, state["embedder"], lib["run"])
    if trace["generation"].get("input_tokens"):
        state["guard"].spend()
    qv = np.array(trace["retrieval"]["query_vector"])
    trace["retrieval"]["query_position"] = lib["galaxy"].project(qv)
    if trace.get("answer"):  # don't remember failures: the next try might work
        state["cache"].put(cache_key, trace)
    # The visitor's own remaining allowance, for the Journey. Added after caching: it is theirs, not the question's.
    return {**trace, "quota": state["guard"].left(visitor)}
