"""
Register a library of PDFs downloaded by hand.

Put them in the library's inbox (its "inbox" folder in pipeline/libraries.py),
one folder per project, and name each one after its doc type:
    data/raw/inbox/<project_id>/pdd.pdf, validation_report.pdf, ...
(A table library such as the electric cars is a CSV, not PDFs: collect/table.py registers it the same way.)

For each file we compute its sha256 fingerprint and:
  - skip it if that fingerprint is already registered (idempotent re-runs),
  - otherwise copy it to data/raw/files/<sha256>.pdf and record it in the
    manifest, matched to an existing row for that project and doc type when
    there is one, or as a new row when there isn't.
"""

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..config import FILES_DIR
from ..db import connect
from ..libraries import LIBRARIES, check

PREFIXES = {"pdd": "pdd", "validation": "validation_report", "vr": "validation_report",
            "mr": "monitoring_report", "monitoring": "monitoring_report"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def doc_type_from_name(name: str) -> str:
    stem = name.lower().split(".")[0]
    for prefix, doc_type in PREFIXES.items():
        if stem.startswith(prefix):
            return doc_type
    return "other"


def run(library: str) -> dict:
    inbox = LIBRARIES[check(library)]["inbox"]
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(inbox.glob("*/*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {inbox}/<folder>/")
    stats = {"new": 0, "already": 0}
    with connect() as conn:
        for pdf in pdfs:
            project_id, digest = pdf.parent.name, sha256_of(pdf)
            found = conn.execute("select library from manifest where sha256 = %s", (digest,)).fetchone()
            if found:
                if found[0] != library:
                    print(f"  WARNING {project_id}/{pdf.name} is already registered in library {found[0]!r}; left there")
                stats["already"] += 1
                continue
            target = FILES_DIR / f"{digest}.pdf"
            shutil.copy2(pdf, target)
            doc_type, now = doc_type_from_name(pdf.name), datetime.now(timezone.utc)
            # Prefer an existing row for this project + doc type that has no file yet.
            row = conn.execute(
                """select id from manifest where library = %s and project_id = %s and doc_type = %s and sha256 is null
                   order by id limit 1""", (library, project_id, doc_type)).fetchone()
            if row:
                conn.execute("update manifest set sha256=%s, local_path=%s, fetched_at=%s where id=%s",
                             (digest, str(target), now, row[0]))
            else:
                conn.execute(
                    """insert into manifest (library, project_id, doc_type, link_text, source_url, sha256, local_path, fetched_at)
                       values (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (library, project_id, doc_type, pdf.name, f"manual://{library}/{project_id}/{pdf.name}",
                     digest, str(target), now))
            conn.commit()
            stats["new"] += 1
            print(f"  registered {project_id}/{pdf.name} ({doc_type}) {digest[:12]}")
    print(f"Done ({library}): {stats['new']} new, {stats['already']} already registered")
    return stats
