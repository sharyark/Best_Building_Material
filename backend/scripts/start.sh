#!/bin/sh
set -eu
alembic upgrade head
python -m app.bootstrap
exec gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "${WEB_CONCURRENCY:-3}" \
    --bind 0.0.0.0:8000 \
    --forwarded-allow-ips "*" \
    --access-logfile - \
    --timeout 60
