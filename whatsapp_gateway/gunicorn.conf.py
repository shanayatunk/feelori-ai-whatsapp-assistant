import os  # Add import
bind = "0.0.0.0:5000"
workers = int(os.getenv('GUNICORN_WORKERS', 2))
worker_class = "gevent"
timeout = 30