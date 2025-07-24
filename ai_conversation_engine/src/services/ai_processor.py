# ai_conversation_engine/src/services/ai_processor.py
import asyncio
import httpx
import structlog
import re
import hashlib
import time
from typing import Dict, List, Tuple, Optional, Any, Protocol
from dataclasses import dataclass
from enum import Enum
from prometheus_client import Counter, Histogram, Gauge
from contextlib import asynccontextmanager
from tenacity import retry, wait_exponential, stop_after_attempt

from src.config import settings
from pydantic import ValidationError
from src.exceptions import AIServiceError, CircuitBreakerOpenError
from src.services.conversation_manager import ConversationManager
from src.services.circuit_breaker import CircuitBreaker
from src.services.sanitizer import InputSanitizer
from src.services.intent_analyzer import IntentAnalyzer, IntentType
from src.services.knowledge_retriever import KnowledgeRetriever
from src.utils.rate_limiter import RateLimiter
from src.utils.cache import CacheManager

logger = structlog.get_logger(__name__)

# --- Enhanced Metrics ---
INTENT_COUNT = Counter('ai_intent_total', 'Total intents processed', ['intent', 'status'])
PROCESSING_TIME = Histogram('ai_processing_seconds', 'Time spent processing messages', ['intent'])
LLM_REQUEST_COUNT = Counter('llm_requests_total', 'Total LLM requests', ['model', 'status'])
ACTIVE_CONVERSATIONS = Gauge('active_conversations', 'Number of active conversations')
CACHE_HIT_RATE = Counter('cache_hits_total', 'Cache hit/miss counter', ['type', 'result'])

# --- Data Classes ---
@dataclass
class ProcessingResult:
    """Result of message processing with metadata."""
    response: str
    intent: IntentType
    processing_time: float
    tokens_used: Optional[int] = None
    cached: bool = False
    error: Optional[str] = None

# --- Protocols & Handlers ---
class MessageHandler(Protocol):
    """Protocol for message handlers."""
    async def handle(self, message: str, context: Dict[str, Any]) -> str: ...

class AsyncAIProcessor:
    """
    Enhanced AI processor with improved error handling, caching, rate limiting,
    and better separation of concerns.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        app_settings: "Settings",
        conversation_manager: ConversationManager,
        cache_manager: Optional[CacheManager] = None,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """Initializes the AI processor with enhanced dependencies."""
        self.settings = app_settings
        self.http_client = http_client
        self.conversation_manager = conversation_manager
        self.cache_manager = cache_manager or CacheManager()
        self.rate_limiter = rate_limiter or RateLimiter(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW
        )

        # API Configuration (No hardcoded keys/models)
        self.api_url = self._build_api_url()
        self.headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.settings.GEMINI_API_KEY
        }

        # Circuit Breakers
        self.llm_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.LLM_FAILURE_THRESHOLD,
            recovery_timeout=self.settings.LLM_RECOVERY_TIMEOUT,
            name="LLM"
        )
        self.ecommerce_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.ECOMMERCE_FAILURE_THRESHOLD,
            recovery_timeout=self.settings.ECOMMERCE_RECOVERY_TIMEOUT,
            name="ECommerce"
        )

        # Services
        self.intent_analyzer = IntentAnalyzer()
        self.knowledge_retriever = KnowledgeRetriever(self.http_client, self.settings)

        # Message handlers registry
        self._handlers: Dict[IntentType, MessageHandler] = {}
        self._register_handlers()

        # Semaphore for concurrent request limiting
        self._request_semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_REQUESTS)

    def _build_api_url(self) -> str:
        """Build the API URL with secure API key handling."""
        if not self.settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY configuration missing")
        # Use the model name from settings
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.GEMINI_MODEL}:generateContent"

    def _register_handlers(self) -> None:
        """Register intent-specific message handlers."""
        self._handlers = {
            IntentType.GREETING: GreetingHandler(),
            IntentType.PRODUCT_QUERY: ProductQueryHandler(self),
            IntentType.PRODUCT_DETAILS_FOLLOWUP: ProductDetailsHandler(self),
            IntentType.ORDER_STATUS: OrderStatusHandler(self),
            IntentType.KNOWLEDGE_BASE_QUERY: KnowledgeQueryHandler(self),
            IntentType.FALLBACK: FallbackHandler(self)
        }

    async def initialize(self) -> None:
        """Initialize async components like the knowledge retriever."""
        try:
            await self.knowledge_retriever.initialize()
            logger.info("Knowledge retriever initialized successfully")
        except Exception:
            logger.warning("Failed to initialize knowledge retriever", exc_info=True)

    async def close(self) -> None:
        """Cleanup resources like cache connections."""
        try:
            await self.cache_manager.close()
            logger.info("AI Processor resources cleaned up")
        except Exception:
            logger.error("Error during AI Processor cleanup", exc_info=True)
            
    async def health_check(self) -> dict:
        """Check the health of the AI processor and its dependencies."""
        kr_health = await self.knowledge_retriever.embedding_service.health_check()
        return {
            "status": "healthy" if kr_health['status'] == 'healthy' else 'unhealthy',
            "dependencies": {
                "knowledge_retriever": kr_health,
                "llm_circuit_breaker": self.llm_circuit_breaker.get_status(),
                "ecommerce_circuit_breaker": self.ecommerce_circuit_breaker.get_status()
            }
        }


    @asynccontextmanager
    async def _processing_context(self, conv_id: str):
        """Context manager for processing with metrics and cleanup."""
        start_time = time.time()
        ACTIVE_CONVERSATIONS.inc()
        try:
            yield
        finally:
            ACTIVE_CONVERSATIONS.dec()
            processing_time = time.time() - start_time
            logger.debug("Message processed", conv_id=conv_id, duration=processing_time)

    async def process_message(
        self, message: str, conv_id: str, platform: str = "web", lang: str = "en", user_id: Optional[str] = None
    ) -> ProcessingResult:
        """Enhanced message processing with comprehensive error handling and metrics."""
        start_time = time.time()

        async with self._processing_context(conv_id):
            try:
                # Rate limiting (uses user_id if available)
                if user_id and not await self.rate_limiter.allow_request(user_id):
                    return ProcessingResult(
                        response="Rate limit exceeded. Please wait.",
                        intent=IntentType.FALLBACK, processing_time=time.time() - start_time, error="rate_limit_exceeded"
                    )

                # Input validation and sanitization
                sanitized_message = await self._validate_and_sanitize_input(message)

                # Check cache first
                cache_key = self._generate_cache_key(sanitized_message)
                cached_response = await self.cache_manager.get(cache_key)
                if cached_response:
                    CACHE_HIT_RATE.labels(type='response', result='hit').inc()
                    return ProcessingResult(
                        response=cached_response['response'], intent=IntentType(cached_response['intent']),
                        processing_time=time.time() - start_time, cached=True
                    )
                CACHE_HIT_RATE.labels(type='response', result='miss').inc()

                # Get conversation history for context
                history = await self.conversation_manager.get_history(conv_id)
                context = {'history': history, 'platform': platform, 'lang': lang, 'conv_id': conv_id}

                # Analyze intent
                intent_result = await self.intent_analyzer.analyze(sanitized_message, context)
                intent = intent_result.intent

                # Process with appropriate handler
                async with self._request_semaphore:
                    handler = self._handlers.get(intent, self._handlers[IntentType.FALLBACK])
                    handler_context = {**context, 'message': sanitized_message, 'intent_result': intent_result}
                    response = await handler.handle(sanitized_message, handler_context)

                # Cache successful non-error responses
                if response and "error" not in response.lower() and "sorry" not in response.lower():
                    await self.cache_manager.set(
                        cache_key, {'response': response, 'intent': intent.value}, ttl=self.settings.CACHE_TTL
                    )

                # Save conversation turn
                await self.conversation_manager.add_turn(conv_id, "user", sanitized_message)
                await self.conversation_manager.add_turn(conv_id, "assistant", response)

                processing_time = time.time() - start_time
                PROCESSING_TIME.labels(intent=intent.value).observe(processing_time)
                INTENT_COUNT.labels(intent=intent.value, status='success').inc()

                return ProcessingResult(response=response, intent=intent, processing_time=processing_time)

            except ValidationError as e:
                INTENT_COUNT.labels(intent='unknown', status='validation_error').inc()
                logger.warning("Validation error during message processing", error=str(e), conv_id=conv_id)
                return ProcessingResult(
                    response="Your message seems to be invalid. Please check and try again.",
                    intent=IntentType.FALLBACK, processing_time=time.time() - start_time, error="validation_error"
                )
            except CircuitBreakerOpenError as e:
                INTENT_COUNT.labels(intent='unknown', status='circuit_breaker').inc()
                logger.warning("Circuit breaker triggered", error=str(e), conv_id=conv_id)
                return ProcessingResult(
                    response=f"A required service is temporarily unavailable ({e.name}). Please try again shortly.",
                    intent=IntentType.FALLBACK, processing_time=time.time() - start_time, error="service_unavailable"
                )
            except Exception as e:
                INTENT_COUNT.labels(intent='unknown', status='error').inc()
                logger.error("Critical error processing message", exc_info=True)
                return ProcessingResult(
                    response="I encountered an unexpected internal error. My team has been notified.",
                    intent=IntentType.FALLBACK, processing_time=time.time() - start_time, error="internal_error"
                )

    async def _validate_and_sanitize_input(self, message: str) -> str:
        """Enhanced input validation and sanitization."""
        if not message or not isinstance(message, str):
            raise ValidationError("Invalid message format: must be a non-empty string")

        if len(message) > self.settings.MAX_MESSAGE_LENGTH:
            raise ValidationError(f"Message exceeds maximum length of {self.settings.MAX_MESSAGE_LENGTH} characters")

        sanitized = InputSanitizer.sanitize(message, strict_mode=True)
        if not sanitized.strip():
            raise ValidationError("Message is empty after sanitization.")
        
        return sanitized

    def _generate_cache_key(self, message: str) -> str:
        """Generate a cache key for the message. Excludes conv_id for better general caching."""
        key_data = f"{message}:{self.settings.CACHE_VERSION}"
        return hashlib.md5(key_data.encode()).hexdigest()

# --- Handler Implementations ---

class GreetingHandler(MessageHandler):
    """Handler for greeting intents."""
    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        history = context.get('history', [])
        if not history or len(history) < 2:
            return "Hello! I'm your AI assistant. How can I help you find products, check order statuses, or answer questions?"
        return "Welcome back! How can I assist you today?"

class ProductQueryHandler(MessageHandler):
    """Handler for product query intents."""
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        intent_result = context['intent_result']
        keywords = intent_result.entities.get('product_name', '').split()
        
        if not keywords:
            return "I can help with that! What kind of products are you looking for?"
        try:
            products = await self._fetch_products(keywords)
            if not products:
                return f"Sorry, I couldn't find any products matching '{' '.join(keywords)}'. You could try different keywords."
            return self._format_product_results(products, keywords)
        except Exception as e:
            logger.error("Product query failed", error=str(e), keywords=keywords)
            return "I'm having trouble searching for products right now. Please try again in a moment."

    @retry(wait=wait_exponential(multiplier=1, min=1, max=5), stop=stop_after_attempt(3))
    async def _fetch_products(self, keywords: List[str]) -> List[Dict]:
        """Fetch products with retries and circuit breaker."""
        async def fetch():
            headers = {"Authorization": f"Bearer {self.processor.settings.INTERNAL_API_KEY}"}
            params = {"keywords": " ".join(keywords), "limit": self.processor.settings.MAX_PRODUCTS_TO_SHOW}
            response = await self.processor.http_client.get(
                self.processor.settings.ECOMMERCE_API_URL, headers=headers, params=params
            )
            response.raise_for_status()
            return response.json()
        return await self.processor.ecommerce_circuit_breaker.call(fetch)

    def _format_product_results(self, products: List[Dict], keywords: List[str]) -> str:
        if len(products) == 1:
            p = products[0]
            return f"I found one product for you:\n- **{p['title']}**: ${p['price']:.2f}"

        product_list = [f"- **{p['title']}**: ${p['price']:.2f}" for p in products]
        response = f"I found these products matching '{' '.join(keywords)}':\n" + "\n".join(product_list)
        response += "\n\nWould you like more details on any of these?"
        return response

class ProductDetailsHandler(MessageHandler):
    # Simplified for brevity; would be similar to ProductQueryHandler
    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        return "This is where I would provide more details about a specific product."

class OrderStatusHandler(MessageHandler):
    """Handler for order status intents."""
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor
    
    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        order_id_match = re.search(r'\b(ORD-\d+|[A-Z0-9-]{8,})\b', message, re.IGNORECASE)
        if not order_id_match:
            return "I can check your order status. Please provide the order ID."
        
        order_id = order_id_match.group(0)
        try:
            # This would call an e-commerce service
            return f"Checking the status for order **{order_id}**. One moment..."
        except Exception:
            return "Sorry, I'm unable to check order statuses right now."

class KnowledgeQueryHandler(MessageHandler):
    """Handler for queries that should be answered by the knowledge base."""
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        search_results = await self.processor.knowledge_retriever.search(message, limit=1)
        if not search_results:
            return await self._fallback_to_llm(message, context)

        best_result = search_results[0]
        if best_result.similarity > 0.8: # High confidence
            return best_result.document.chunk_text
        else:
            return await self._fallback_to_llm(message, context, kb_context=best_result.document.chunk_text)

    async def _fallback_to_llm(self, message: str, context: Dict[str, Any], kb_context: Optional[str] = None) -> str:
        """If KB search is inconclusive, use the general LLM for a response."""
        fallback_handler = self.processor._handlers[IntentType.FALLBACK]
        # Prepend KB context to the user's message if available
        if kb_context:
            context['message'] = f"Use the following context to answer the question:\nContext: {kb_context}\n\nQuestion: {message}"
        else:
             context['message'] = message
        return await fallback_handler.handle(context['message'], context)

class FallbackHandler(MessageHandler):
    """Fallback handler that uses the generative LLM."""
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    @retry(wait=wait_exponential(multiplier=1, min=1, max=5), stop=stop_after_attempt(3))
    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        """Generates a response using the configured Gemini model."""
        payload = {
            "contents": [{"parts": [{"text": message}]}]
        }
        async def generate():
            LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='attempt').inc()
            response = await self.processor.http_client.post(
                self.processor.api_url, headers=self.processor.headers, json=payload
            )
            response.raise_for_status()
            LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='success').inc()
            return response.json()['candidates'][0]['content']['parts'][0]['text']

        try:
            return await self.processor.llm_circuit_breaker.call(generate)
        except Exception as e:
            LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='failure').inc()
            logger.error("LLM generation failed after retries", error=str(e))
            raise AIServiceError("The AI service failed to generate a response.") from e