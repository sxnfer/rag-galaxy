"""Database helpers: one connection function and a schema bootstrap."""

import contextlib
import os
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from .config import DATABASE_URL

ENTRA_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def _password() -> str | None:
    """On Azure the database URL has no password: the app proves who it is with
    its managed identity and gets a short-lived token, used as the password.
    Locally (Docker Postgres) the URL carries its own password and this returns None."""
    if urlparse(DATABASE_URL).password or not os.environ.get("AZURE_CLIENT_ID"):
        return None
    from azure.identity import ManagedIdentityCredential  # only needed on Azure

    return ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"]).get_token(ENTRA_SCOPE).token


def _open(autocommit: bool) -> psycopg.Connection:
    password = _password()
    return psycopg.connect(DATABASE_URL, autocommit=autocommit, **({"password": password} if password else {}))


def connect() -> psycopg.Connection:
    conn = _open(autocommit=False)
    # Makes Postgres `vector` columns come back as NumPy arrays.
    # It fails when the extension isn't created yet; init_db will create it.
    with contextlib.suppress(psycopg.ProgrammingError):
        register_vector(conn)
    return conn


def as_np(v) -> np.ndarray:
    """pgvector may hand back its own Vector type; the pipeline always works in NumPy."""
    return v.to_numpy() if hasattr(v, "to_numpy") else np.asarray(v)


def init_db() -> None:
    sql = (Path(__file__).parent / "schema.sql").read_text()
    with _open(autocommit=True) as conn:
        conn.execute(sql)
    print("Schema ready.")
