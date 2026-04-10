#!/bin/sh
set -e
if [ -n "$DATABASE_URL" ]; then
  poetry run python -m alembic upgrade head
fi
exec poetry run "$@"
