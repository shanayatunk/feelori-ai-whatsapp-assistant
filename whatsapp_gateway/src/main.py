# whatsapp_gateway/src/main.py

import os
import uuid
import time
import signal
import sys
from flask import Flask, g, request, jsonify, Response

from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Core Imports ---
from src.config import settings  # Use Pydantic settings
from src.models import db
from src.routes.webhook import webhook_bp
from src.routes.message import message_bp
from src.exceptions import APIError
from src.monitoring import (
    webhook_processing_time,
    error_counter,
    track_message,
    generate_latest
)

# --- Structured Logging ---
import structlog
logger = structlog.get_logger(__name__).bind(service="whatsapp_gateway")

# --- App Initialization ---
app = Flask(__name__)

# --- Configuration ---
# Load configuration directly from the validated Pydantic settings object
app.config['SQLALCHEMY_DATABASE_URI'] = settings.DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB

# --- Extensions ---
CORS(app, origins=settings.CORS_ORIGINS.split(','))
db.init_app(app)
migrate = Migrate(app, db)
limiter = Limiter(app, key_func=get_remote_address, default_limits=["200 per minute"])

# --- Blueprints ---
app.register_blueprint(webhook_bp, url_prefix='/api')
app.register_blueprint(message_bp, url_prefix='/api')

# --- Request Hooks & Monitoring ---
@app.before_request
def before_request_handler():
    """Set up request context and start timer."""
    g.start_time = time.time()
    g.correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(correlation_id=g.correlation_id)
    logger.info("Request started", path=request.path, method=request.method)

@app.after_request
def after_request_handler(response):
    """Log request completion and record metrics."""
    duration = time.time() - g.start_time
    webhook_processing_time.labels(
        method=request.method,
        endpoint=request.path,
        status_code=response.status_code
    ).observe(duration)
    
    logger.info(
        "Request finished",
        path=request.path,
        method=request.method,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2)
    )
    return response

# --- Core Routes ---
@app.route('/api/health')
def health_check():
    """Provides a health check endpoint for monitoring."""
    # This is a simplified health check. A production-ready one would check DB/Redis connections.
    return jsonify({"status": "healthy"}), 200

@app.route('/metrics')
def metrics():
    """Exposes Prometheus metrics."""
    return Response(generate_latest(), mimetype='text/plain')

# --- Error Handling ---
@app.errorhandler(APIError)
def handle_api_error(error: APIError):
    """Handle custom API errors."""
    error_counter.labels(error_type='api_error', endpoint=request.path).inc()
    return jsonify({
        'error': error.message,
        'details': error.details
    }), error.status_code

@app.errorhandler(Exception)
def handle_uncaught_exception(e: Exception):
    """Handle unexpected errors."""
    logger.error("Unhandled exception caught", exc_info=e)
    error_counter.labels(error_type='uncaught_exception', endpoint=request.path).inc()
    return jsonify({'error': 'Internal Server Error'}), 500

# --- Graceful Shutdown ---
def shutdown_handler(sig, frame):
    logger.info("Shutdown signal received. Shutting down gracefully.")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

if __name__ == '__main__':
    # Pydantic handles configuration validation on startup.
    # If any required env vars are missing, the app will fail to start.
    logger.info("Starting Flask application", host="0.0.0.0", port=5000)
    app.run(host='0.0.0.0', port=5000)