#!/bin/sh
set -e

echo "Running Alembic migrations..."
if alembic upgrade head; then
    echo "Migrations complete."
else
    echo "Warning: Alembic migration failed — DB may be unreachable or schema already current. Continuing..."
fi

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
