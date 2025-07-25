# whatsapp_gateway/src/main.py

import os
import uuid
import time
import signal
import sys
import logging

from flask import Flask, g, request, jsonify, Response
from flask_migrate import Migrate
from flask_cors import CORS
import structlog

# --- Core Application Imports ---
from shared.config import settings
from src.models.base import db
from src.routes.webhook import webhook_bp, limiter  # <-- Import limiter from webhook
from src.routes.message import message_bp
from shared.exceptions import APIError
from src.monitoring import (
    webhook_processing_time,
    error_counter,
    track_message,
    generate_latest
)

# --- Initialize Logger ---
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__).bind(service="whatsapp_gateway")


def create_app():
    """
    Create and configure the Flask application using the factory pattern.
    """
    app = Flask(__name__)

    # --- Configuration ---
    app.config['SQLALCHEMY_DATABASE_URI'] = settings.DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = settings.SECRET_KEY.get_secret_value()
    app.config['DEBUG'] = settings.DEBUG

    # --- Initialize Extensions ---
    CORS(app, origins=settings.ALLOWED_ORIGINS.split(','))
    db.init_app(app)
    Migrate(app, db)
    
    # --- CORRECTED: Initialize Limiter with the app context ---
    limiter.init_app(app)

    # --- Register Blueprints ---
    app.register_blueprint(webhook_bp, url_prefix='/api')
    app.register_blueprint(message_bp, url_prefix='/api')
    logger.info("Blueprints registered successfully.")

    # --- Request Hooks & Monitoring ---
    @app.before_request
    def before_request_handler():
        """Set up request context and start timer."""
        g.start_time = time.time()
        g.correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(correlation_id=g.correlation_id)
        logger.info(f"Request started", method=request.method, path=request.path)

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
            f"Request finished",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=round(duration * 1000, 2)
        )
        return response

    # --- Core Routes ---
    @app.route('/api/health')
    def health_check():
        """Provides a health check endpoint for monitoring."""
        try:
            # FIXED: Use text() for SQLAlchemy 2.0 compatibility
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db_status = "healthy"
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            db_status = "unhealthy"
        
        health_data = {
            "status": "healthy" if db_status == "healthy" else "unhealthy",
            "service": "whatsapp_gateway",
            "database": db_status
        }
        status_code = 200 if health_data["status"] == "healthy" else 503
        return jsonify(health_data), status_code

    @app.route('/metrics')
    def metrics():
        """Exposes Prometheus metrics."""
        return Response(generate_latest(), mimetype='text/plain')

    # --- Error Handling ---
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        """Handle custom defined API errors."""
        error_counter.labels(error_type='api_error', endpoint=request.path).inc()
        logger.error("API Error", message=error.message, details=getattr(error, 'details', None))
        return jsonify({'error': error.message, 'details': error.details}), error.status_code

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(Exception)
    def handle_uncaught_exception(e: Exception):
        """Handle all other unexpected errors."""
        logger.error("Unhandled exception", error=str(e), exc_info=True)
        error_counter.labels(error_type='uncaught_exception', endpoint=request.path).inc()
        return jsonify({'error': 'Internal Server Error'}), 500

    return app

# --- Create App for Gunicorn/Flask CLI ---
app = create_app()

# --- Graceful Shutdown Handler ---
def shutdown_handler(sig, frame):
    logger.info("Shutdown signal received, exiting.")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

if __name__ == '__main__':
    # FIXED: This block is for local development - use port 5000 to match Dockerfile
    logger.info("Starting Flask application in debug mode.")
    app.run(host='0.0.0.0', port=5000, debug=True)