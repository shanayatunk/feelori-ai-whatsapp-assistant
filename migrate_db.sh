#!/bin/bash

echo "=== WhatsApp Gateway Database Migration Script ==="

export PATH="/opt/venv/bin:$PATH"
export PYTHONPATH=/app
export FLASK_APP=src.main

cd /app

echo "1. Checking Flask installation..."
/opt/venv/bin/python -c "import flask; print('Flask version:', flask.__version__)"

echo "2. Initializing Flask-Migrate..."
if [ ! -d "migrations" ]; then
    /opt/venv/bin/flask db init
fi

echo "3. Creating migration..."
/opt/venv/bin/flask db migrate -m "Create conversation and message tables"

echo "4. Applying migrations..."
/opt/venv/bin/flask db upgrade

echo "=== Migration completed! ==="