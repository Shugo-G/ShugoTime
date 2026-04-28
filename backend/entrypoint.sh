#!/bin/sh
set -e

mkdir -p "$(dirname "${SQLITE_PATH:-/app/db.sqlite3}")" "${FICHADAS_DIR:-/app/fichadas}"

python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 1 \
  --worker-class gthread \
  --threads 4 \
  --timeout 120 \
  --access-logfile -
