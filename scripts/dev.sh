#!/usr/bin/env bash
# One command to run RAG Galaxy locally:  ./scripts/dev.sh
# Starts Postgres (Docker), creates the tables, then the API and the frontend.
# Ctrl+C stops the API and frontend; `docker compose down` stops Postgres.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example; add your ANTHROPIC_API_KEY to it."; }

docker compose up -d --wait db

cd backend
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
.venv/bin/python -m pipeline init-db
.venv/bin/uvicorn app.main:app --reload --port 8000 &
API=$!
trap 'kill $API 2>/dev/null' EXIT

cd ../frontend
[ -d node_modules ] || npm install
npm run dev
