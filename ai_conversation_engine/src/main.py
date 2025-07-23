# ai_conversation_engine/src/main.py

import logging
import uuid
import time
import httpx
from contextlib import asynccontextmanager
from quart import Quart, request, Response
from quart_cors import cors
from prometheus_client import Counter, Histogram, generate_latest
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from src.config import settings
from src.routes.conversation import conversation_bp
from src.services.ai_processor import AsyncAIProcessor
from src.services.conversation_manager import ConversationManager
from src.services.knowledge_retriever import KnowledgeRetriever
from src.auth import require_api_key

# --- OpenTelemetry Setup ---
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(OTLPSpanExporter())
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
        record.correlation_id = getattr(request, 'correlation_id', 'N/A')
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

# --- Prometheus Metrics ---
REQUEST_COUNT = Counter('ai_requests_total', 'Total requests processed', ['endpoint', 'http_status'])
REQUEST_DURATION = Histogram('ai_request_duration_seconds', 'Request duration in seconds', ['endpoint'])
INTENT_COUNT = Counter('ai_intent_total', 'Total intents processed', ['intent'])
CONVERSATION_LENGTH = Histogram('conversation_length_turns', 'Number of turns per conversation')
USER_SATISFACTION = Counter('user_satisfaction', 'User satisfaction ratings', ['rating'])

@asynccontextmanager
async def lifespan(app: Quart):
    """
    Manages application startup and shutdown, initializing and closing resources.
    
    Args:
        app: The Quart application instance.
    """
    logger.info("Application startup...")
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
    knowledge_retriever = KnowledgeRetriever(http_client=http_client, settings=settings)
    await knowledge_retriever.initialize()
    
    app.http_client = http_client
    app.ai_processor = ai_processor
    app.conversation_manager = conversation_manager
    app.knowledge_retriever = knowledge_retriever
    
    yield

    logger.info("Application shutting down...")
    await app.ai_processor.close()
    await app.http_client.aclose()
    if app.conversation_manager:
        app.conversation_manager.close()

def create_app():
    """
    Creates and configures the Quart application.
    
    Returns:
        Quart: Configured Quart application instance.
    """
    app = Quart(__name__, lifespan=lifespan)
    app = cors(app, allow_origin=settings.ALLOWED_ORIGINS.split(','))
    logger.info(f"CORS enabled for origins: {settings.ALLOWED_ORIGINS.split(',')}")

    @app.before_request
    def before_request_handler():
        """Sets up request metadata before processing."""
        request.start_time = time.time()
        request.correlation_id = str(uuid.uuid4())

    @app.after_request
    async def after_request_handler(response):
        """
        Records metrics after each request.
        
        Args:
            response: The HTTP response object.
            
        Returns:
            Response: The modified response object.
        """
        endpoint = request.path
        status_code = response.status_code
        duration = time.time() - request.start_time
        REQUEST_COUNT.labels(endpoint=endpoint, http_status=status_code).inc()
        REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
        return response

    @app.route('/metrics')
    @require_api_key
    async def metrics():
        """Exposes Prometheus metrics."""
        return Response(generate_latest(), mimetype='text/plain')

    app.register_blueprint(conversation_bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)