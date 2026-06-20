#!/usr/bin/env sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  if [ -f "/app/backend/alembic.ini" ]; then
    echo "Running database migrations..."
    cd /app/backend
    alembic upgrade head
  else
    echo "Skipping database migrations: /app/backend/alembic.ini not found."
  fi
fi

exec "$@"
