#!/bin/sh
# api    : run database migrations, then serve the API
# worker : run the arq worker (crew runs execute in subprocesses)
# *      : run any other command (e.g. python -m app.crew.run ...)
set -eu

case "${1:-api}" in
  api)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}" \
      --workers "${API_WORKERS:-2}" --no-server-header
    ;;
  worker)
    exec arq app.worker.jobs.WorkerSettings
    ;;
  *)
    exec "$@"
    ;;
esac
