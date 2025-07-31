# ai_conversation_engine/src/services/ai_processor.py
# Corrected and verified version

import asyncio
import httpx
import structlog
import re
import hashlib
import time
import traceback
from typing import Dict, List, Tuple, Optional, Any, Protocol
from dataclasses import dataclass
from enum import Enum
from prometheus_client import Counter, Histogram, Gauge
from contextlib import asynccontextmanager
from tenacity import retry, wait_exponential, stop_after_attempt
from pydantic import BaseModel, validator

from shared.config import Settings
from pydantic import ValidationError
from shared.exceptions import AIServiceError, CircuitBreakerOpenError
from src.services.conversation_manager import ConversationManager
from src.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from src.services.sanitizer import InputSanitizer
from src.services.intent_analyzer import IntentAnalyzer, IntentType
from src.services.knowledge_retriever import KnowledgeRetriever
from src.utils.rate_limiter import RateLimiter
from shared.cache import CacheManager

logger = structlog.get_logger(__name__)

# --- Configuration Models ---
class AIProcessorConfig(BaseModel):
    """Validated configuration for the AI Processor."""
    MAX_MESSAGE_LENGTH: int = 4096
    MAX_CONCURRENT_REQUESTS: int = 50
    MAX_CONVERSATION_TURNS: int = 20  # Max history before pruning
    HIGH_SIMILARITY_THRESHOLD: float = 0.8
    MIN_LLM_RESPONSE_LENGTH: int = 5
    
    @validator('MAX_MESSAGE_LENGTH')
    def validate_message_length(cls, v):
        if not 10 <= v <= 8192:
            raise ValueError('Max message length must be between 10 and 8192')
        return v

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

def safe_process_gemini_response(response: httpx.Response, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """Safely process Gemini API response with detailed error handling."""
    log = logger.bind(conversation_id=conversation_id)
    try:
        if response is None:
            log.error("Gemini response object is None")
            return {"error": "Empty response object from AI service"}
        
        if response.status_code != 200:
            log.error("Gemini API returned error status", status_code=response.status_code, response_text=response.text)
            return {"error": f"Gemini API error: HTTP {response.status_code}"}
        
        try:
            json_data = response.json()
        except Exception as e:
            log.error("Failed to parse Gemini response JSON", error=str(e), response_text=response.text)
            return {"error": "Invalid JSON response from Gemini API"}

        if "error" in json_data:
            error_msg = json_data["error"].get("message", "Unknown API error")
            log.error("Gemini API returned error", error=error_msg)
            return {"error": f"Gemini API error: {error_msg}"}

        if not json_data.get("candidates"):
            finish_reason = json_data.get("promptFeedback", {}).get("blockReason")
            log.warning("Gemini response missing 'candidates' field", finish_reason=finish_reason or "Unknown", raw_response=response.text)
            return {"error": f"No candidates in Gemini response. Reason: {finish_reason}"}

        candidate = json_data["candidates"][0]
        
        finish_reason = candidate.get("finishReason")
        if finish_reason and finish_reason != "STOP":
            log.warning("Gemini response was blocked or incomplete", finish_reason=finish_reason)
            return {"error": f"Response blocked: {finish_reason}"}
        
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        
        if not parts or "text" not in parts[0]:
            log.error("Empty or malformed 'parts' in Gemini response content.", raw_response=response.text)
            return {"error": "Invalid or empty content parts in response"}
        
        text = parts[0]["text"].strip()
        if not text:
            log.error("Extracted text from Gemini response is empty.", raw_response=response.text)
            return {"error": "Empty text content"}
            
        return {"success": True, "text": text}

    except Exception as e:
        log.error("Unexpected error processing Gemini response", error=str(e), error_type=type(e).__name__, traceback=traceback.format_exc())
        return {"error": f"Unexpected processing error: {str(e)}"}

class AsyncAIProcessor:
    """Enhanced AI processor with failover, validated config, and dynamic handlers."""
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        conversation_manager: ConversationManager,
        cache_manager: Optional[CacheManager] = None,
        rate_limiter: Optional[RateLimiter] = None
    ):
        self.settings = settings
        self.config = AIProcessorConfig()
        self.http_client = http_client
        self.conversation_manager = conversation_manager
        self.cache_manager = cache_manager or CacheManager()
        self.rate_limiter = rate_limiter or RateLimiter(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW
        )

        self.gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.GEMINI_MODEL}:generateContent"
        self.gemini_headers = {"Content-Type": "application/json", "x-goog-api-key": self.settings.GEMINI_API_KEY.get_secret_value()}
        self.openai_api_url = "https://api.openai.com/v1/chat/completions"
        self.openai_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.settings.OPENAI_API_KEY.get_secret_value()}"}

        self.gemini_circuit_breaker = CircuitBreaker(CircuitBreakerConfig(name="LLM_Gemini"))
        self.openai_circuit_breaker = CircuitBreaker(CircuitBreakerConfig(name="LLM_OpenAI"))
        self.ecommerce_circuit_breaker = CircuitBreaker(CircuitBreakerConfig(name="ECommerce"))

        self.intent_analyzer = IntentAnalyzer()
        
        try:
            self.knowledge_retriever = KnowledgeRetriever(self.http_client, self.settings)
        except Exception as e:
            logger.warning("Failed to initialize knowledge retriever", error=str(e))
            self.knowledge_retriever = None

        self._handlers: Dict[IntentType, MessageHandler] = {}
        self._register_default_handlers()
        self._request_semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENT_REQUESTS)

    def register_handler(self, intent: IntentType, handler: MessageHandler):
        """Allow dynamic handler registration for extensibility."""
        logger.info("Registering new handler", intent=intent.value, handler=type(handler).__name__)
        self._handlers[intent] = handler

    def _register_default_handlers(self) -> None:
        """Register default, intent-specific message handlers."""
        self.register_handler(IntentType.GREETING, GreetingHandler())
        self.register_handler(IntentType.PRODUCT_QUERY, ProductQueryHandler(self))
        self.register_handler(IntentType.PRODUCT_DETAILS_FOLLOWUP, ProductDetailsHandler(self))
        self.register_handler(IntentType.ORDER_STATUS, OrderStatusHandler(self))
        self.register_handler(IntentType.KNOWLEDGE_BASE_QUERY, KnowledgeQueryHandler(self))
        self.register_handler(IntentType.FALLBACK, FallbackHandler(self))

    async def initialize(self) -> None:
        """Initialize async components like the knowledge retriever."""
        try:
            if self.knowledge_retriever:
                await self.knowledge_retriever.initialize()
                logger.info("Knowledge retriever initialized successfully")
            else:
                logger.warning("Knowledge retriever not available")
        except Exception as e:
            logger.warning("Failed to initialize knowledge retriever", error=str(e), exc_info=True)

    async def close(self) -> None:
        """Cleanup resources like cache connections."""
        try:
            if self.cache_manager:
                await self.cache_manager.close()
            logger.info("AI Processor resources cleaned up")
        except Exception as e:
            logger.error("Error during AI Processor cleanup", error=str(e), exc_info=True)
            
    async def health_check(self) -> dict:
        """Check the health of the AI processor and its dependencies."""
        try:
            if self.knowledge_retriever and hasattr(self.knowledge_retriever, 'embedding_service'):
                kr_health = await self.knowledge_retriever.embedding_service.health_check()
            else:
                kr_health = {"status": "unavailable", "reason": "Knowledge retriever not initialized"}
        except Exception as e:
            kr_health = {"status": "error", "error": str(e)}
            
        return {
            "status": "healthy" if kr_health.get('status') == 'healthy' else 'degraded',
            "dependencies": {
                "knowledge_retriever": kr_health,
                "gemini_circuit_breaker": self.gemini_circuit_breaker.get_stats(),
                "openai_circuit_breaker": self.openai_circuit_breaker.get_stats(),
                "ecommerce_circuit_breaker": self.ecommerce_circuit_breaker.get_stats()
            }
        }

    async def process_message(
        self, message: str, conv_id: str, platform: str = "web", lang: str = "en", user_id: Optional[str] = None
    ) -> ProcessingResult:
        """Main message processing pipeline with comprehensive error handling."""
        start_time = time.time()
        log = logger.bind(conv_id=conv_id)
        
        async with self._processing_context(conv_id):
            try:
                # Step 1: Validate and sanitize input
                try:
                    sanitized_message = await self._validate_and_sanitize_input(message)
                except ValidationError as e:
                    log.warning("Input validation failed", error=str(e))
                    return ProcessingResult(
                        response="I'm sorry, but your message appears to be invalid. Please try rephrasing it.",
                        intent=IntentType.FALLBACK,
                        processing_time=time.time() - start_time,
                        error="validation_error"
                    )
                
                # Step 2: Get conversation history
                try:
                    history = await self.conversation_manager.get_history(conv_id)
                    await self._prune_conversation_history(conv_id, history)
                except Exception as e:
                    log.warning("Failed to get conversation history", error=str(e))
                    history = []

                # Step 3 & 4: Analyze intent and check cache
                context = {'history': history, 'platform': platform, 'lang': lang, 'conv_id': conv_id}
                intent_result = None
                
                try:
                    intent_result = await self.intent_analyzer.analyze(sanitized_message, context)
                    intent = intent_result.intent
                    
                    cache_key = self._generate_cache_key(sanitized_message, intent)
                    if cached_response := await self.cache_manager.get(cache_key):
                        CACHE_HIT_RATE.labels(type='response', result='hit').inc()
                        return ProcessingResult(
                            response=cached_response, 
                            intent=intent, 
                            processing_time=time.time()-start_time, 
                            cached=True
                        )
                    CACHE_HIT_RATE.labels(type='response', result='miss').inc()
                    
                    handler = self._handlers.get(intent, self._handlers[IntentType.FALLBACK])

                except Exception as e:
                    log.warning("Intent analysis or cache check failed, using fallback", error=str(e))
                    intent = IntentType.FALLBACK
                    intent_result = type('obj', (object,), {'intent': intent, 'entities': {}})()
                    handler = self._handlers[IntentType.FALLBACK]
                    cache_key = self._generate_cache_key(sanitized_message, intent)

                # Step 5: Process with the determined handler
                response = ""
                async with self._request_semaphore:
                    handler_context = {**context, 'message': sanitized_message, 'intent_result': intent_result}
                    try:
                        response = await handler.handle(sanitized_message, handler_context)
                    except Exception as e:
                        log.error("Handler failed, using fallback", error=str(e), intent=intent.value, exc_info=True)
                        fallback_handler = self._handlers[IntentType.FALLBACK]
                        response = await fallback_handler.handle(sanitized_message, handler_context)

                # Step 6: Validate and cache response
                if self._validate_llm_response(response):
                    try:
                        await self.cache_manager.set(cache_key, response, ttl=self.settings.CACHE_TTL)
                    except Exception as e:
                        log.warning("Failed to cache response", error=str(e))

                # Step 7: Update conversation history using the corrected method
                try:
                    current_history = await self.conversation_manager.get_history(conv_id)
                    current_history.append({"role": "user", "content": sanitized_message})
                    current_history.append({"role": "assistant", "content": response})
                    await self.conversation_manager.save_history(conv_id, current_history)
                except Exception as e:
                    log.warning("Failed to update conversation history", error=str(e), exc_info=True)
                
                # Final step: Return successful result
                processing_time = time.time() - start_time
                PROCESSING_TIME.labels(intent=intent.value).observe(processing_time)
                INTENT_COUNT.labels(intent=intent.value, status='success').inc()
                
                return ProcessingResult(
                    response=response, 
                    intent=intent, 
                    processing_time=processing_time
                )

            except Exception as e:
                log.error("Critical error processing message", error=str(e), error_type=type(e).__name__, exc_info=True)
                INTENT_COUNT.labels(intent='unknown', status='critical_error').inc()
                return ProcessingResult(
                    response="I encountered an unexpected internal error. My team has been notified.",
                    intent=IntentType.FALLBACK,
                    processing_time=time.time() - start_time,
                    error="internal_error"
                )

    def _validate_llm_response(self, response_text: str) -> bool:
        """Validate LLM response for basic quality and safety."""
        if not response_text or len(response_text.strip()) < self.config.MIN_LLM_RESPONSE_LENGTH:
            logger.warning("LLM response failed validation", length=len(response_text.strip()))
            return False
        return True

    async def _prune_conversation_history(self, conv_id: str, history: List[Dict]) -> None:
        """Keep only recent conversation turns to manage memory and token limits."""
        if len(history) > self.config.MAX_CONVERSATION_TURNS:
            pruned_history = history[-self.config.MAX_CONVERSATION_TURNS:]
            # Note: The manager's save_history already trims, but this explicit call
            # using a different method name (`set_history`) might be desired.
            # We'll use save_history for consistency, assuming `set_history` might not exist.
            await self.conversation_manager.save_history(conv_id, pruned_history)
            logger.info("Pruned conversation history", conv_id=conv_id, original_len=len(history), new_len=len(pruned_history))

    def _generate_cache_key(self, message: str, intent: IntentType) -> str:
        """Include context (intent) in cache key for better hit rates."""
        cache_data = f"{message}:{intent.value}:{self.settings.CACHE_VERSION}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    async def _validate_and_sanitize_input(self, message: str) -> str:
        if not message or not isinstance(message, str):
            raise ValidationError("Message must be a non-empty string")
        if len(message) > self.config.MAX_MESSAGE_LENGTH:
            raise ValidationError(f"Message too long: {len(message)} > {self.config.MAX_MESSAGE_LENGTH}")
        
        try:
            sanitized = InputSanitizer.sanitize(message, strict_mode=True)
        except Exception as e:
            logger.warning("Sanitization failed, using original message", error=str(e))
            sanitized = message.strip()
            
        if not sanitized.strip():
            raise ValidationError("Message is empty after sanitization.")
        return sanitized

    @asynccontextmanager
    async def _processing_context(self, conv_id: str):
        start_time = time.time()
        ACTIVE_CONVERSATIONS.inc()
        try:
            yield
        finally:
            ACTIVE_CONVERSATIONS.dec()
            logger.debug("Message processed", conv_id=conv_id, duration=time.time() - start_time)
            
    def _handle_processing_error(self, error: Exception, conv_id: str, start_time: float) -> ProcessingResult:
        error_type = "validation_error" if isinstance(error, ValidationError) else "service_unavailable"
        user_message = "Your message seems to be invalid." if isinstance(error, ValidationError) else "A required service is temporarily unavailable. Please try again shortly."
        INTENT_COUNT.labels(intent='unknown', status=error_type).inc()
        logger.warning(f"Error during message processing: {error_type}", error=str(error), conv_id=conv_id)
        return ProcessingResult(response=user_message, intent=IntentType.FALLBACK, processing_time=time.time() - start_time, error=error_type)

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
        intent_result = context.get('intent_result')
        if not intent_result or not hasattr(intent_result, 'entities'):
            return "I can help with that! What kind of products are you looking for?"
            
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
            headers = {"Authorization": f"Bearer {self.processor.settings.INTERNAL_API_KEY.get_secret_value()}"}
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
            title = p.get('title', 'Unknown Product')
            price = p.get('price', 0.0)
            return f"I found one product for you:\n- **{title}**: ${price:.2f}"

        product_list = [f"- **{p.get('title', 'Unknown Product')}**: ${p.get('price', 0.0):.2f}" for p in products]
        response = f"I found these products matching '{' '.join(keywords)}':\n" + "\n".join(product_list)
        response += "\n\nWould you like more details on any of these?"
        return response

class ProductDetailsHandler(MessageHandler):
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor
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
            return f"Checking the status for order **{order_id}**. One moment..."
        except Exception:
            return "Sorry, I'm unable to check order statuses right now."

class KnowledgeQueryHandler(MessageHandler):
    """Handler for queries that should be answered by the knowledge base."""
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        if not self.processor.knowledge_retriever:
            fallback_handler = self.processor._handlers[IntentType.FALLBACK]
            return await fallback_handler.handle(message, context)
            
        try:
            search_results = await self.processor.knowledge_retriever.search(message, limit=1)
            if search_results and search_results[0].similarity > self.processor.config.HIGH_SIMILARITY_THRESHOLD:
                return search_results[0].document.chunk_text
            return await self._fallback_to_llm(message, context, kb_context=search_results[0].document.chunk_text if search_results else None)
        except Exception as e:
            logger.warning("Knowledge query failed, using fallback", error=str(e))
            fallback_handler = self.processor._handlers[IntentType.FALLBACK]
            return await fallback_handler.handle(message, context)
    
    async def _fallback_to_llm(self, message: str, context: Dict[str, Any], kb_context: Optional[str] = None) -> str:
        fallback_handler = self.processor._handlers[IntentType.FALLBACK]
        if kb_context:
            context['message'] = f"Use this context to answer: {kb_context}\n\nQuestion: {message}"
        else:
            context['message'] = message
        return await fallback_handler.handle(context['message'], context)

class FallbackHandler(MessageHandler):
    """Implements Gemini -> OpenAI -> Static Message failover logic."""
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        conv_id = context.get('conv_id')
        log = logger.bind(conv_id=conv_id)
        
        try:
            log.info("Attempting response generation with primary LLM (Gemini).")
            return await self._call_gemini(message, conv_id)
        except Exception as gemini_error:
            log.warning("Primary LLM (Gemini) failed. Failing over to secondary LLM (OpenAI).", error=str(gemini_error))
            try:
                return await self._call_openai(message)
            except Exception as openai_error:
                log.error("Secondary LLM (OpenAI) also failed. Using static fallback.", 
                          gemini_error=str(gemini_error), openai_error=str(openai_error))
                return "I'm having trouble connecting to my AI services right now. Please try your request again in a moment."

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def _call_gemini(self, message: str, conv_id: Optional[str] = None) -> str:
        """Makes a request to the Gemini API, protected by its circuit breaker."""
        async def generate():
            LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='attempt').inc()
            
            try:
                response = await self.processor.http_client.post(
                    self.processor.gemini_api_url,
                    headers=self.processor.gemini_headers,
                    json={"contents": [{"parts": [{"text": message}]}]},
                    timeout=30.0
                )
                
                result = safe_process_gemini_response(response, conv_id)
                if "error" in result:
                    LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='error').inc()
                    raise AIServiceError(f"Gemini response parsing failed: {result['error']}")
                
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='success').inc()
                return result["text"]
                
            except httpx.TimeoutException:
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='timeout').inc()
                raise AIServiceError("Gemini API request timed out")
            except httpx.HTTPStatusError as e:
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='http_error').inc()
                raise AIServiceError(f"Gemini API HTTP error: {e.response.status_code}")
            except Exception as e:
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.GEMINI_MODEL, status='error').inc()
                raise AIServiceError(f"Gemini API error: {str(e)}")
                
        return await self.processor.gemini_circuit_breaker.call(generate)

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def _call_openai(self, message: str) -> str:
        """Makes a request to the OpenAI API, protected by its circuit breaker."""
        async def generate():
            LLM_REQUEST_COUNT.labels(model=self.processor.settings.OPENAI_MODEL, status='attempt').inc()
            
            try:
                payload = {
                    "model": self.processor.settings.OPENAI_MODEL, 
                    "messages": [{"role": "user", "content": message}],
                    "max_tokens": 500,
                    "temperature": 0.7
                }
                response = await self.processor.http_client.post(
                    self.processor.openai_api_url, 
                    headers=self.processor.openai_headers, 
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                json_data = response.json()
                message_content = json_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if not message_content:
                    LLM_REQUEST_COUNT.labels(model=self.processor.settings.OPENAI_MODEL, status='error').inc()
                    raise AIServiceError("Empty or missing 'content' in OpenAI response.")
                    
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.OPENAI_MODEL, status='success').inc()
                return message_content
                
            except httpx.TimeoutException:
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.OPENAI_MODEL, status='timeout').inc()
                raise AIServiceError("OpenAI API request timed out")
            except httpx.HTTPStatusError as e:
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.OPENAI_MODEL, status='http_error').inc()
                raise AIServiceError(f"OpenAI API HTTP error: {e.response.status_code}")
            except Exception as e:
                LLM_REQUEST_COUNT.labels(model=self.processor.settings.OPENAI_MODEL, status='error').inc()
                raise AIServiceError(f"OpenAI API error: {str(e)}")
                
        return await self.processor.openai_circuit_breaker.call(generate)