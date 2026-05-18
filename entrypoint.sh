#!/bin/sh

echo "=== Running database migrations ==="
alembic upgrade head
MIGRATION_EXIT=$?

if [ $MIGRATION_EXIT -ne 0 ]; then
    echo "=== WARNING: Migrations failed with exit code $MIGRATION_EXIT, starting app anyway ==="
else
    echo "=== Migrations completed successfully ==="
fi

echo "=== Starting server on port ${PORT:-8080} ==="
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8080}"
