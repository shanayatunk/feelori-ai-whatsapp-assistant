#!/bin/sh

# Set the path to the Python executable in the venv
VENV_PYTHON="/home/appuser/venv/bin/python"

echo "--- Starting WhatsApp Gateway Service ---"

# Set environment variables
export PYTHONPATH="/home/appuser:$PYTHONPATH"
export FLASK_APP="src.main"

# Wait for database to be ready
echo "--- Waiting for database to be ready ---"
until $VENV_PYTHON -c "
import sys
sys.path.insert(0, '/home/appuser')
try:
    from src.config import settings
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.close()
    print('Database is ready!')
except Exception as e:
    print(f'Database not ready: {e}')
    sys.exit(1)
" 2>/dev/null; do
  echo "Waiting for database..."
  sleep 2
done

echo "--- Checking if Flask migration is needed ---"

# Check if we have migrations directory and flask-migrate is working
if [ -d "migrations" ]; then
    echo "--- Found migrations directory, running database migrations ---"
    
    # Initialize migrations if not already done
    if [ ! -f "migrations/alembic.ini" ]; then
        echo "--- Initializing migrations ---"
        $VENV_PYTHON -m flask db init --directory migrations
        if [ $? -ne 0 ]; then
            echo "--- Failed to initialize migrations, continuing without migrations ---"
        fi
    fi
    
    # Create migration if models have changed
    echo "--- Creating migration if needed ---"
    $VENV_PYTHON -m flask db migrate -m "Auto migration" --directory migrations 2>/dev/null || echo "--- No new migrations needed ---"
    
    # Run migrations
    echo "--- Running database migrations ---"
    $VENV_PYTHON -m flask db upgrade --directory migrations
    
    # Check if migrations succeeded
    if [ $? -eq 0 ]; then
        echo "--- Database migrations completed successfully ---"
    else
        echo "--- Database migrations failed, but continuing startup ---"
        echo "--- The application will try to create tables dynamically ---"
    fi
else
    echo "--- No migrations directory found ---"
    echo "--- Will attempt to create database tables dynamically ---"
    
    # Try to create tables using SQLAlchemy
    $VENV_PYTHON -c "
import sys
sys.path.insert(0, '/home/appuser')
try:
    from src.main import app
    from src.models import db
    with app.app_context():
        db.create_all()
        print('Database tables created successfully!')
except Exception as e:
    print(f'Failed to create tables: {e}')
" || echo "--- Table creation failed, continuing anyway ---"
fi

echo "--- Database setup completed ---"

# Test import of main application
echo "--- Testing application imports ---"
$VENV_PYTHON -c "
import sys
sys.path.insert(0, '/home/appuser')
try:
    from src.main import app
    print('Application imported successfully!')
except ImportError as e:
    print(f'Import error: {e}')
    print('Available modules in src:')
    import os
    if os.path.exists('/home/appuser/src'):
        for f in os.listdir('/home/appuser/src'):
            if f.endswith('.py'):
                print(f'  - {f}')
    sys.exit(1)
except Exception as e:
    print(f'Other error: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "--- Application import test failed. Aborting startup. ---"
    exit 1
fi

echo "--- Application is ready to start ---"

# Execute the command passed from the Dockerfile's CMD
exec "$@"