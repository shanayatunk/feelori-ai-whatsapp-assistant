#!/bin/sh

# Set the correct path to the Python executable in the venv
VENV_PYTHON="/home/appuser/venv/bin/python"

echo "--- Starting WhatsApp Gateway Service ---"

# Debug: Show which secret files are mounted
echo "--- Checking Docker secrets ---"
if [ -d "/run/secrets" ]; then
    echo "Available secrets:"
    ls -la /run/secrets/
else
    echo "❌ No /run/secrets directory found"
fi

# Wait for the database to be ready
echo "--- Waiting for database to be ready ---"
max_attempts=30
attempt=0

until [ $attempt -ge $max_attempts ]; do
    attempt=$((attempt + 1))
    echo "Database connection attempt $attempt/$max_attempts..."

    # Test database connection
    output=$($VENV_PYTHON -c "
import sys
sys.path.insert(0, '/home/appuser')
try:
    from shared.config import settings
    import psycopg2
    # Extract the database URL value
    db_url = settings.DATABASE_URL.get_secret_value() if hasattr(settings.DATABASE_URL, 'get_secret_value') else str(settings.DATABASE_URL)
    print('Attempting database connection...')
    psycopg2.connect(db_url)
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
" 2>&1)

    # Check the exit code of the python command
    if [ $? -eq 0 ]; then
        echo "✅ Database is ready!"
        break
    else
        echo "❌ Connection failed: $output"
        if [ $attempt -ge $max_attempts ]; then
            echo "❌ Failed to connect to database after $max_attempts attempts. Exiting."
            exit 1
        fi
        echo "⏳ Database not ready yet, waiting 2 seconds..."
        sleep 2
    fi
done

echo "--- Database is available. Starting server. ---"

# Execute the command passed from the Dockerfile's CMD (e.g., hypercorn)
exec "$@"