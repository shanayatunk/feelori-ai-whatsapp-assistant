#!/bin/sh

# This script waits for the database to be ready and then executes
# the main command for the service (e.g., starting the web server or celery worker).
# It no longer handles database migrations.

set -e # Exit immediately if a command exits with a non-zero status.

VENV_PYTHON="/opt/venv/bin/python"

# The first argument to the script can be 'wait-for-db-only'
# This allows a container (like the migrations service) to use this script
# just for the wait logic, without starting a long-running process.
if [ "$1" = 'wait-for-db-only' ]; then
    # Shift the arguments, so the main exec "$@" at the end doesn't re-run this.
    shift
else
    echo "--- Starting Service ---"
fi

# Wait for the database to be ready
echo "--- Waiting for database to be ready ---"
max_attempts=30
attempt=1

# This python command is more robust. It reads the DB URL directly from the
# secret file path defined in the environment variables.
until [ $attempt -gt $max_attempts ]; do
    echo "Database connection attempt $attempt/$max_attempts..."
    
    output=$($VENV_PYTHON -c "
import sys, os, psycopg2
try:
    db_url_file = os.getenv('DATABASE_URL_FILE')
    if not db_url_file:
        raise ValueError('DATABASE_URL_FILE environment variable not set.')
    with open(db_url_file, 'r') as f:
        db_url = f.read().strip()
    psycopg2.connect(db_url)
except Exception as e:
    print(e, file=sys.stderr)
    exit(1)
" 2>&1)

    if [ $? -eq 0 ]; then
        echo "✅ Database is ready!"
        break
    else
        echo "❌ Connection failed: $output"
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Failed to connect to database after $max_attempts attempts. Exiting."
            exit 1
        fi
        echo "⏳ Database not ready yet, waiting 2 seconds..."
        sleep 2
    fi
    attempt=$((attempt + 1))
done


# --- AUTOMATIC DATABASE MIGRATION SECTION HAS BEEN REMOVED ---
# Migrations are now handled by the dedicated 'migrations' service in docker-compose.yml.
# This script's only job is to wait for the DB and start the main process.

echo "--- Setup complete. Starting main process. ---"
# Execute the command passed from the Dockerfile's CMD (e.g., hypercorn or celery)
# or any command passed to the 'migrations' service after the wait logic.
exec "$@"