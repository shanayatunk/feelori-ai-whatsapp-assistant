# gunicorn.conf.py for ai-conversation-engine

import multiprocessing

# Worker settings
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gevent'

# --- CORRECTED TIMEOUT ---
# Increased timeout to 90 seconds to allow for slow LLM API responses
timeout = 90

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Binding
bind = '0.0.0.0:5001'