#!/bin/sh
set -e

mkdir -p /app/instance /app/storage

if [ "${SKIP_DB_UPGRADE:-0}" != "1" ]; then
  python -m flask db upgrade -d flask_migrations
fi

if [ "$1" = "gunicorn" ]; then
  set -- "$@" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-300}" \
    --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
    --access-logfile "-" \
    --error-logfile "-"
fi

exec "$@"
