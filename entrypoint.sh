#!/bin/sh

echo "=== Running database migrations ==="
MIGRATION_OUTPUT=$(alembic upgrade head 2>&1)
MIGRATION_EXIT=$?

echo "$MIGRATION_OUTPUT"

if [ $MIGRATION_EXIT -ne 0 ]; then
    echo "=== MIGRATION ERROR (exit $MIGRATION_EXIT) ==="
    echo "$MIGRATION_OUTPUT"
    echo "=== Starting app anyway ==="
else
    echo "=== Migrations completed successfully ==="
fi

echo "=== Starting server on port ${PORT:-8080} ==="
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8080}"
