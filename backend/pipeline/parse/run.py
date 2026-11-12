"""M2 runner: parse every registered PDF that hasn't been parsed yet (or all, with force)."""

import json

from psycopg.types.json import Jsonb

from ..db import connect
from .pdf import parse_pdf
from .quality import check_page, report


def run(force: bool = False) -> list[dict]:
    out = []
    with connect() as conn:
        docs = conn.execute(
            """select m.sha256, m.local_path, m.project_id, m.doc_type from manifest m
               where m.sha256 is not null
                 and (%s or not exists (select 1 from quality_reports q where q.doc_sha256 = m.sha256))
               order by m.project_id""", (force,)).fetchall()
        for sha, path, pid, dtype in docs:
            try:
                pages = parse_pdf(path)
            except Exception as e:
                print(f"  FAILED {pid} {dtype}: {e}")
                out.append({"project_id": pid, "doc_type": dtype, "error": str(e)})
                continue
            flags = [check_page(p) for p in pages]
            conn.execute("delete from pages where doc_sha256 = %s", (sha,))
            for p, fl in zip(pages, flags, strict=True):
                conn.execute(
                    """insert into pages (doc_sha256, page_no, text, headings, n_tables, tables_md, is_scanned, flags)
                       values (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (sha, p.page_no, p.text, p.headings, len(p.tables_md), p.tables_md, p.is_scanned, fl))
            rep = report(pages, flags)
            conn.execute(
                """insert into quality_reports (doc_sha256, report) values (%s, %s)
                   on conflict (doc_sha256) do update set report = excluded.report, created_at = now()""",
                (sha, Jsonb(rep)))
            conn.commit()
            print(f"  {pid} {dtype}: {json.dumps(rep)}")
            out.append({"project_id": pid, "doc_type": dtype, **rep})
    print(f"Parsed {len(out)} documents")
    return out
