"""Settings in one place. Values come from the environment (.env), never from code."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # the rag-galaxy folder
load_dotenv(ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag")

DATA = ROOT / "data"
FILES_DIR = DATA / "raw" / "files"            # registered files (CSVs, PDFs), named by their hash

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
