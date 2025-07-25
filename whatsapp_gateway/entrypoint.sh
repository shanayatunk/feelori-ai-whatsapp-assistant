#!/bin/bash

# Set the path to the Python executable in the venv
VENV_PYTHON="/home/appuser/venv/bin/python"

echo "--- Starting WhatsApp Gateway Service ---"

# Check if Python executable exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Python executable not found at $VENV_PYTHON"
    echo "Available files in venv/bin:"
    ls -la /home/appuser/venv/bin/ || echo "venv/bin directory not found"
    echo "Falling back to system Python"
    VENV_PYTHON="python3"
fi

# Wait for the database to be ready with better error handling
echo "--- Waiting for database to be ready ---"
max_attempts=30
attempt=0

until [ $attempt -ge $max_attempts ]; do
    attempt=$((attempt + 1))
    echo "Database connection attempt $attempt/$max_attempts..."
    
    # Try to connect to the database with proper error handling
    if $VENV_PYTHON -c "
import sys
import os
sys.path.insert(0, '/home/appuser/src')
sys.path.insert(0, '/home/appuser/shared')

try:
    # Try importing from different possible locations
    try:
        from shared.config import settings
        db_url = settings.DATABASE_URL
    except ImportError:
        try:
            from config import settings
            db_url = settings.DATABASE_URL
        except ImportError:
            # Fallback to environment variables
            db_url = os.environ.get('DATABASE_URL', 'postgresql://ai_assistant:ai_assistant_password@postgres:5432/ai_assistant')
    
    import psycopg2
    
    # Debug: Print the DATABASE_URL (without password)
    print(f'Attempting to connect to: {db_url.split(\"@\")[1] if \"@\" in db_url else \"masked_url\"}')
    
    # Try to connect to the database
    conn = psycopg2.connect(db_url)
    conn.close()
    print('✅ Database connection successful!')
    sys.exit(0)
except ImportError as e:
    print(f'❌ Import error: {e}')
    print('Trying direct connection without config...')
    
    # Fallback to direct connection
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='postgres',
            port=5432,
            database='ai_assistant',
            user='ai_assistant',
            password='ai_assistant_password'
        )
        conn.close()
        print('✅ Direct connection successful!')
        sys.exit(0)
    except Exception as e2:
        print(f'❌ Direct connection also failed: {e2}')
        sys.exit(1)
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
" 2>&1; then
        echo "--- Database is ready! ---"
        break
    else
        if [ $attempt -ge $max_attempts ]; then
            echo "❌ Failed to connect to database after $max_attempts attempts"
            echo "--- Debugging information ---"
            echo "Environment variables:"
            env | grep -E "(DATABASE_URL|POSTGRES_)" || echo "No database environment variables found"
            echo "--- Python executable info ---"
            echo "Using Python: $VENV_PYTHON"
            $VENV_PYTHON --version || echo "Failed to get Python version"
            echo "--- Python path info ---"
            $VENV_PYTHON -c "import sys; print('Python path:'); [print(p) for p in sys.path]" || echo "Failed to get Python path"
            exit 1
        fi
        echo "⏳ Database not ready yet, waiting 2 seconds..."
        sleep 2
    fi
done

echo "--- Database is available. Starting server. ---"
echo "--- Note: DB migrations must be run manually using 'docker-compose run...' ---"

# Execute the command passed from the Dockerfile's CMD (e.g., hypercorn)
exec "$@"