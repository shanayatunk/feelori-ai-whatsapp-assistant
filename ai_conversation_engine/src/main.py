# ai_conversation_engine/src/main.py

import logging
import uuid
import time
import httpx
from contextlib import asynccontextmanager
from quart import Quart, request, Response, has_request_context
from quart_cors import cors
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


from shared.config import settings
from src.routes.conversation import conversation_bp
from src.routes.intent import intent_bp
from src.routes.knowledge import knowledge_bp
from src.services.ai_processor import AsyncAIProcessor
from src.services.conversation_manager import ConversationManager
from src.services.knowledge_retriever import KnowledgeRetriever
from src.auth import require_api_key

# (Your OpenTelemetry, Logging, and Prometheus setup remains the same...)
# --- OpenTelemetry Setup ---
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Use the environment variable for the OTLP endpoint
otlp_exporter = OTLPSpanExporter(
    endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
)

# Pass the configured exporter to the span processor
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# --- Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

class CorrelationIDFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.correlation_id = getattr(request, 'correlation_id', 'N/A')
        else:
            record.correlation_id = 'STARTUP'
        return True

formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(correlation_id)s] - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.addFilter(CorrelationIDFilter())
root_logger = logging.getLogger()
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)
logger = structlog.get_logger()

# --- PROMETHEUS FIX: Use Custom Registry ---
CUSTOM_REGISTRY = CollectorRegistry()

def get_or_create_metric(metric_class, name, description, labels=None, registry=None):
    registry = registry or CUSTOM_REGISTRY
    for metric in registry._collector_to_names.keys():
        if hasattr(metric, '_name') and metric._name == name:
            logger.info(f"Reusing existing metric: {name}")
            return metric
    try:
        if labels:
            return metric_class(name, description, labels, registry=registry)
        else:
            return metric_class(name, description, registry=registry)
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            logger.warning(f"Metric {name} already exists, retrieving existing instance")
            for metric in registry._collector_to_names.keys():
                if hasattr(metric, '_name') and metric._name == name:
                    return metric
        raise e

REQUEST_COUNT = get_or_create_metric(
    Counter, 'ai_requests_total', 'Total requests processed', ['endpoint', 'http_status']
)
REQUEST_DURATION = get_or_create_metric(
    Histogram, 'ai_request_duration_seconds', 'Request duration in seconds', ['endpoint']
)
INTENT_COUNT = get_or_create_metric(
    Counter, 'ai_intent_total', 'Total intents processed', ['intent', 'status']
)


def create_app():
    """
    Creates and configures the Quart application.
    """
    app = Quart(__name__)
    app = cors(app, allow_origin=settings.ALLOWED_ORIGINS.split(','))
    logger.info(f"CORS enabled for origins: {settings.ALLOWED_ORIGINS.split(',')}")



    @app.before_serving
    async def startup():
        logger.info("Application startup...")
        try:
            http_client = httpx.AsyncClient(
                timeout=settings.REQUEST_TIMEOUT,
                limits=httpx.Limits(
                    max_keepalive_connections=settings.HTTP_MAX_KEEPALIVE,
                    max_connections=settings.HTTP_MAX_CONNECTIONS
                )
            )
            conversation_manager = ConversationManager(settings=settings)
            ai_processor = AsyncAIProcessor(
                http_client=http_client,
                settings=settings,
                conversation_manager=conversation_manager
            )
            knowledge_retriever = KnowledgeRetriever(http_client=http_client, app_settings=settings)
            await knowledge_retriever.initialize()

            app.http_client = http_client
            app.ai_processor = ai_processor
            app.conversation_manager = conversation_manager
            app.knowledge_retriever = knowledge_retriever

            logger.info("Application startup completed successfully")

        except Exception as e:
            logger.error(f"Error during application startup: {e}")
            raise

    @app.after_serving
    async def shutdown():
        logger.info("Application shutting down...")
        try:
            if hasattr(app, 'http_client') and app.http_client:
                await app.http_client.aclose()
            logger.info("Application shutdown completed successfully")
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")

    @app.before_request
    def before_request_handler():
        request.start_time = time.time()
        request.correlation_id = str(uuid.uuid4())

    @app.after_request
    async def after_request_handler(response):
        try:
            endpoint = request.path
            status_code = response.status_code
            duration = time.time() - request.start_time
            REQUEST_COUNT.labels(endpoint=endpoint, http_status=status_code).inc()
            REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")
        return response

    @app.route('/health')
    async def health_check():
        return {"status": "healthy", "timestamp": time.time()}

    @app.route('/metrics')
    @require_api_key
    async def metrics():
        try:
            return Response(generate_latest(CUSTOM_REGISTRY), mimetype='text/plain')
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return Response("Error generating metrics", status=500)

    @app.errorhandler(500)
    async def internal_server_error(error):
        logger.error(f"Internal server error: {error}")
        return {"error": "Internal server error"}, 500

    @app.errorhandler(404)
    async def not_found(error):
        return {"error": "Endpoint not found"}, 404

    # Register blueprints
    app.register_blueprint(conversation_bp)
    app.register_blueprint(intent_bp)
    app.register_blueprint(knowledge_bp)
    
    return app

# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        workers=1,
        log_level="info"
    )