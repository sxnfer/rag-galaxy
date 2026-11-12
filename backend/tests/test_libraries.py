"""Libraries: every search is filtered to one library, inside the search itself."""

import uuid

import numpy as np
import pytest

from pipeline.chunk.search import RUN_FILTER, _run_where, hnsw_index_name, sql_exact
from pipeline.libraries import LIBRARIES, ORDER, check, is_table, run_of


def test_known_libraries_and_order():
    assert ORDER == ["ev"] and set(ORDER) == set(LIBRARIES)
    assert check("ev") == "ev"
    for retired in ("nasa", "arsenal", "carbon"):   # nasa in plan v2; arsenal and carbon for the electric cars
        with pytest.raises(ValueError):
            check(retired)


def test_a_table_library_has_one_fixed_run():
    assert is_table("ev")
    assert run_of("ev", "fixed", 300) == ("cards", 0)      # whatever was asked for
    assert LIBRARIES["ev"]["table"].exists()


def test_run_filter_and_index_name_include_the_library():
    assert RUN_FILTER.startswith("library = %s")
    assert hnsw_index_name(("ev", "cards", 0, "m")) != hnsw_index_name(("docs", "fixed", 300, "m"))
    assert "library = 'ev'" in _run_where(("ev", "cards", 0, "m"))
    with pytest.raises(ValueError):
        _run_where(("ev'; drop table chunks; --", "fixed", 300, "m"))
    with pytest.raises(ValueError):
        hnsw_index_name(("ev; drop table chunks", "fixed", 300, "m"))


def _db():
    try:
        from pipeline.db import connect
        conn = connect()
        conn.execute("select 1 from chunks limit 1")
        conn.rollback()
        return conn
    except Exception:
        pytest.skip("no local database")


def test_exact_search_never_crosses_libraries():
    """Two libraries, one chunk each, identical vectors: each search sees only its own."""
    conn = _db()
    model = f"test-{uuid.uuid4().hex[:8]}"  # a model name no real run uses, so real chunks are excluded
    v = np.zeros(384, dtype=np.float32); v[0] = 1.0
    ids = {}
    try:
        for lib in ("ev", "test-other"):
            sha = uuid.uuid4().hex
            conn.execute("insert into manifest (library, project_id, doc_type, source_url, sha256) values (%s,%s,%s,%s,%s)",
                         (lib, "test", "other", f"test://{sha}", sha))
            ids[lib] = conn.execute(
                """insert into chunks (library, doc_sha256, chunker, chunk_size, ord, page_start, page_end,
                                       breadcrumb, text, model, model_version, embedding)
                   values (%s,%s,'fixed',300,0,1,1,'t','t',%s,'1',%s) returning id""", (lib, sha, model, v)).fetchone()[0]
        for lib in ("ev", "test-other"):
            hits = sql_exact(conn, v, (lib, "fixed", 300, model), k=5)
            assert [h.chunk_id for h in hits] == [ids[lib]]
    finally:
        conn.rollback()  # nothing is kept
        conn.close()
