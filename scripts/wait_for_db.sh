#!/bin/bash
# Wait for PostgreSQL to be ready. Used in Docker entrypoints.
set -e

HOST="${DB_HOST:-localhost}"
PORT="${DB_PORT:-5432}"
USER="${DB_USER:-sutram}"

echo "Waiting for PostgreSQL at $HOST:$PORT..."
until pg_isready -h "$HOST" -p "$PORT" -U "$USER" -q; do
  sleep 1
done
echo "PostgreSQL is ready."
