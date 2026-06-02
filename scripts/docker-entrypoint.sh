#!/usr/bin/env sh
set -eu

echo "[entrypoint] Waiting for database..."
python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    print("[entrypoint] DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)

engine = create_engine(database_url, pool_pre_ping=True)
for attempt in range(1, 61):
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        print("[entrypoint] Database is ready")
        break
    except OperationalError:
        if attempt == 60:
            print("[entrypoint] Database did not become ready in time", file=sys.stderr)
            raise
        time.sleep(2)
PY

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Starting application..."
exec "$@"
