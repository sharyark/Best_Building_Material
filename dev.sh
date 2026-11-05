#!/usr/bin/env bash
# Local development: starts Postgres (Docker), the API (:8000) and the web app (:5173).
# Run it as `./dev.sh` (not `source dev.sh`). Ctrl+C stops the API and web app; the DB keeps running.
#   docker compose -f docker-compose.dev.yml down   # to stop the DB too
# `./dev.sh --no-demo` (or ./dev_without_data.sh) never loads demo data: an empty database gets only the
# first admin login, the cash account and the chart of accounts; a database with data is left as it is.
# If sourced, run in a child bash instead: set -e / Ctrl+C would otherwise close the user's terminal.
if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  bash "${BASH_SOURCE[0]}" "$@"
  return $?
fi
set -euo pipefail
NO_DEMO=0
if [ "${1:-}" = "--no-demo" ]; then NO_DEMO=1; fi
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT=$PWD

echo "==> Starting database"
docker compose -f docker-compose.dev.yml up -d
until docker compose -f docker-compose.dev.yml exec -T db pg_isready -U hisaab >/dev/null 2>&1; do sleep 1; done

cd "$ROOT/backend"
[ -f .env ] || { cp .env.example .env; echo "==> Created backend/.env from .env.example"; }
if [ ! -x .venv/bin/python ]; then
  echo "==> Creating Python environment (first run)"
  python3 -m venv .venv
  .venv/bin/pip install -e ".[dev]"
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Migrating database"
alembic upgrade head

if [ "$NO_DEMO" = 1 ]; then
  echo "==> No demo data: making sure the first admin, cash account and chart exist"
  python -m app.bootstrap
else
  echo "==> Loading demo data (skipped if the database already has data)"
  python -m app.seed || true
fi

cleanup() { echo; echo "==> Stopping API and web app"; kill 0 2>/dev/null || true; }
trap cleanup INT TERM EXIT

echo "==> Starting API on http://127.0.0.1:8000"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &

echo "==> Starting web app on http://127.0.0.1:5173"
cd "$ROOT/frontend"
[ -d node_modules ] || npm ci
npm run dev -- --host 127.0.0.1 &

wait
