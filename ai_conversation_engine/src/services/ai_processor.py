# ai_conversation_engine/src/services/ai_processor.py

import asyncio
import httpx
import json
import structlog
import re
import hashlib
from typing import Dict, List, Tuple, Optional, Any, Protocol
from dataclasses import dataclass
from enum import Enum
from prometheus_client import Counter, Histogram, Gauge
from contextlib import asynccontextmanager
import time

from src.config import Settings
from src.exceptions import CircuitBreakerOpenError, AIServiceError, ValidationError
from src.services.conversation_manager import ConversationManager
from src.services.circuit_breaker import CircuitBreaker, CircuitBreakerError
from src.services.sanitizer import InputSanitizer
from src.services.intent_analyzer import IntentAnalyzer, IntentType
from src.services.knowledge_retriever import KnowledgeRetriever
from src.utils.rate_limiter import RateLimiter
from src.utils.cache import CacheManager

logger = structlog.get_logger(__name__)

# Enhanced Metrics
INTENT_COUNT = Counter('ai_intent_total', 'Total intents processed', ['intent', 'status'])
PROCESSING_TIME = Histogram('ai_processing_seconds', 'Time spent processing messages', ['intent'])
LLM_REQUEST_COUNT = Counter('llm_requests_total', 'Total LLM requests', ['model', 'status'])
ACTIVE_CONVERSATIONS = Gauge('active_conversations', 'Number of active conversations')
CACHE_HIT_RATE = Counter('cache_hits_total', 'Cache hit/miss counter', ['type', 'result'])

@dataclass
class ProcessingResult:
    """Result of message processing with metadata."""
    response: str
    intent: IntentType
    processing_time: float
    tokens_used: Optional[int] = None
    cached: bool = False
    error: Optional[str] = None

@dataclass
class ProductInfo:
    """Structured product information."""
    title: str
    price: float
    description: str
    id: Optional[str] = None
    image_url: Optional[str] = None
    availability: Optional[str] = None

class MessageHandler(Protocol):
    """Protocol for message handlers."""
    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        ...

class AsyncAIProcessor:
    """
    Enhanced AI processor with improved error handling, caching, rate limiting,
    and better separation of concerns.
    """
    
    def __init__(
        self, 
        http_client: httpx.AsyncClient, 
        settings: Settings, 
        conversation_manager: ConversationManager,
        cache_manager: Optional[CacheManager] = None,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """
        Initializes the AI processor with enhanced dependencies.

        Args:
            http_client: The HTTP client for external API calls.
            settings: Application configuration.
            conversation_manager: Manages conversation history and caching.
            cache_manager: Optional cache manager for response caching.
            rate_limiter: Optional rate limiter for API calls.
        """
        self.settings = settings
        self.http_client = http_client
        self.conversation_manager = conversation_manager
        self.cache_manager = cache_manager or CacheManager()
        self.rate_limiter = rate_limiter or RateLimiter(
            max_requests=settings.MAX_REQUESTS_PER_MINUTE,
            time_window=60
        )
        
        # API Configuration
        self.api_url = self._build_api_url()
        self.headers = {"Content-Type": "application/json"}
        
        # Circuit Breakers with enhanced configuration
        self.llm_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.LLM_FAILURE_THRESHOLD,
            recovery_timeout=self.settings.LLM_RECOVERY_TIMEOUT,
            expected_exception=AIServiceError
        )
        self.ecommerce_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.ECOMMERCE_FAILURE_THRESHOLD,
            recovery_timeout=self.settings.ECOMMERCE_RECOVERY_TIMEOUT,
            expected_exception=httpx.HTTPError
        )
        
        # Services
        self.intent_analyzer = IntentAnalyzer()
        self.knowledge_retriever = None  # Lazy initialization
        
        # Message handlers registry
        self._handlers: Dict[IntentType, MessageHandler] = {}
        self._register_handlers()
        
        # Semaphore for concurrent request limiting
        self._request_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)

    def _build_api_url(self) -> str:
        """Build the API URL with proper error handling."""
        if not self.settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required")
        return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.settings.GEMINI_API_KEY}"

    def _register_handlers(self) -> None:
        """Register intent-specific message handlers."""
        self._handlers = {
            IntentType.GREETING: GreetingHandler(),
            IntentType.PRODUCT_QUERY: ProductQueryHandler(self),
            IntentType.PRODUCT_DETAILS_FOLLOWUP: ProductDetailsHandler(self),
            IntentType.ORDER_STATUS: OrderStatusHandler(self),
            IntentType.FALLBACK: FallbackHandler(self)
        }

    async def initialize(self) -> None:
        """Initialize async components."""
        if not self.knowledge_retriever:
            try:
                self.knowledge_retriever = KnowledgeRetriever(self.http_client, self.settings)
                await self.knowledge_retriever.initialize()
                logger.info("Knowledge retriever initialized successfully")
            except Exception as e:
                logger.warning("Failed to initialize knowledge retriever", error=str(e))

    async def close(self) -> None:
        """Cleanup resources."""
        try:
            if self.knowledge_retriever:
                await self.knowledge_retriever.close()
            
            if self.http_client and not self.http_client.is_closed:
                await self.http_client.aclose()
                
            await self.cache_manager.close()
            logger.info("AI Processor resources cleaned up")
        except Exception as e:
            logger.error("Error during cleanup", error=str(e))

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
        self, 
        message: str, 
        conv_id: str, 
        platform: str = "web", 
        lang: str = "en",
        user_id: Optional[str] = None
    ) -> ProcessingResult:
        """
        Enhanced message processing with comprehensive error handling and metrics.

        Args:
            message: The user's input message.
            conv_id: Unique conversation identifier.
            platform: The platform from which the message originates.
            lang: The language code.
            user_id: Optional user identifier for rate limiting.

        Returns:
            ProcessingResult: Comprehensive processing result with metadata.
        """
        start_time = time.time()
        
        async with self._processing_context(conv_id):
            try:
                # Rate limiting
                if user_id and not await self.rate_limiter.allow_request(user_id):
                    return ProcessingResult(
                        response="Rate limit exceeded. Please wait before sending another message.",
                        intent=IntentType.FALLBACK,
                        processing_time=time.time() - start_time,
                        error="rate_limit_exceeded"
                    )

                # Input validation and sanitization
                sanitized_message = await self._validate_and_sanitize_input(message)
                if not sanitized_message:
                    return ProcessingResult(
                        response="I didn't receive your message. Could you please try again?",
                        intent=IntentType.FALLBACK,
                        processing_time=time.time() - start_time,
                        error="empty_message"
                    )

                # Check cache first
                cache_key = self._generate_cache_key(sanitized_message, conv_id)
                cached_response = await self.cache_manager.get(cache_key)
                if cached_response:
                    CACHE_HIT_RATE.labels(type='response', result='hit').inc()
                    return ProcessingResult(
                        response=cached_response['response'],
                        intent=IntentType(cached_response['intent']),
                        processing_time=time.time() - start_time,
                        cached=True
                    )
                CACHE_HIT_RATE.labels(type='response', result='miss').inc()

                # Get conversation history
                history = await self.conversation_manager.get_history(conv_id)
                
                # Analyze intent with context
                context = {
                    'history': history,
                    'platform': platform,
                    'lang': lang,
                    'conv_id': conv_id
                }
                
                intent, extracted_data = await self._analyze_user_input(
                    sanitized_message, context
                )
                
                # Process with appropriate handler
                async with self._request_semaphore:
                    response = await self._process_with_handler(
                        intent, sanitized_message, extracted_data, context
                    )

                # Cache successful responses
                if response and not any(err in response.lower() for err in ['error', 'sorry', 'unavailable']):
                    await self.cache_manager.set(
                        cache_key, 
                        {'response': response, 'intent': intent.value},
                        ttl=self.settings.CACHE_TTL
                    )

                # Save conversation turn
                await self._save_conversation_turn(
                    conv_id, sanitized_message, response, history
                )

                processing_time = time.time() - start_time
                PROCESSING_TIME.labels(intent=intent.value).observe(processing_time)
                INTENT_COUNT.labels(intent=intent.value, status='success').inc()

                return ProcessingResult(
                    response=response,
                    intent=intent,
                    processing_time=processing_time
                )

            except ValidationError as e:
                INTENT_COUNT.labels(intent='unknown', status='validation_error').inc()
                logger.warning("Validation error", error=str(e), conv_id=conv_id)
                return ProcessingResult(
                    response="I couldn't process your message. Please check your input and try again.",
                    intent=IntentType.FALLBACK,
                    processing_time=time.time() - start_time,
                    error="validation_error"
                )
            
            except CircuitBreakerError as e:
                INTENT_COUNT.labels(intent='unknown', status='circuit_breaker').inc()
                logger.warning("Circuit breaker triggered", error=str(e), conv_id=conv_id)
                return ProcessingResult(
                    response="Service temporarily unavailable. Please try again in a few moments.",
                    intent=IntentType.FALLBACK,
                    processing_time=time.time() - start_time,
                    error="service_unavailable"
                )
            
            except Exception as e:
                INTENT_COUNT.labels(intent='unknown', status='error').inc()
                logger.error("Critical error processing message", 
                           conv_id=conv_id, error=str(e), exc_info=True)
                return ProcessingResult(
                    response="I encountered an unexpected error. Please try again later.",
                    intent=IntentType.FALLBACK,
                    processing_time=time.time() - start_time,
                    error="internal_error"
                )

    async def _validate_and_sanitize_input(self, message: str) -> str:
        """Enhanced input validation and sanitization."""
        if not message or not isinstance(message, str):
            raise ValidationError("Invalid message format")
        
        if len(message) > self.settings.MAX_MESSAGE_LENGTH:
            raise ValidationError("Message too long")
        
        sanitized = InputSanitizer.sanitize(message)
        if not sanitized.strip():
            return ""
        
        return sanitized

    def _generate_cache_key(self, message: str, conv_id: str) -> str:
        """Generate a cache key for the message."""
        key_data = f"{message}:{conv_id}:{self.settings.CACHE_VERSION}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def _analyze_user_input(
        self, message: str, context: Dict[str, Any]
    ) -> Tuple[IntentType, Dict[str, Any]]:
        """Enhanced intent analysis with context awareness."""
        try:
            intent = await self.intent_analyzer.analyze(message, context)
            extracted_data = await self._extract_data_for_intent(intent, message, context)
            return intent, extracted_data
        except Exception as e:
            logger.error("Intent analysis failed", error=str(e))
            return IntentType.FALLBACK, {}

    async def _extract_data_for_intent(
        self, intent: IntentType, message: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract relevant data based on intent."""
        extracted = {}
        
        if intent == IntentType.PRODUCT_QUERY:
            # Enhanced keyword extraction
            keywords = self._extract_product_keywords(message)
            extracted['keywords'] = keywords
            extracted['filters'] = self._extract_product_filters(message)
            
        elif intent == IntentType.PRODUCT_DETAILS_FOLLOWUP:
            # Try to find product reference in history
            product_title = self._extract_product_reference(message, context.get('history', []))
            if product_title:
                extracted['product_title'] = product_title
                
        elif intent == IntentType.ORDER_STATUS:
            order_id = self._extract_order_id(message)
            if order_id:
                extracted['order_id'] = order_id
                
        return extracted

    def _extract_product_keywords(self, message: str) -> List[str]:
        """Enhanced product keyword extraction."""
        # Remove common stop words and extract meaningful terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [word.lower().strip() for word in re.findall(r'\b\w+\b', message)]
        return [word for word in words if word not in stop_words and len(word) > 2]

    def _extract_product_filters(self, message: str) -> Dict[str, Any]:
        """Extract product filters from message."""
        filters = {}
        
        # Price range extraction
        price_match = re.search(r'under\s*\$?(\d+)|below\s*\$?(\d+)|less\s*than\s*\$?(\d+)', message, re.IGNORECASE)
        if price_match:
            price = next(filter(None, price_match.groups()))
            filters['max_price'] = float(price)
        
        # Category extraction
        categories = ['electronics', 'clothing', 'books', 'home', 'sports', 'beauty']
        for category in categories:
            if category in message.lower():
                filters['category'] = category
                break
        
        return filters

    def _extract_product_reference(self, message: str, history: List[Dict]) -> Optional[str]:
        """Extract product reference from message and history."""
        # Look for recent product mentions in history
        for turn in reversed(history[-10:]):  # Check last 10 turns
            if turn.get('role') == 'assistant' and 'products' in turn.get('content', '').lower():
                # Extract product names from assistant's response
                lines = turn['content'].split('\n')
                for line in lines:
                    if line.strip().startswith('-') and ':' in line:
                        product_name = line.split(':')[0].strip('- ')
                        if any(word in message.lower() for word in product_name.lower().split()):
                            return product_name
        return None

    def _extract_order_id(self, message: str) -> Optional[str]:
        """Extract order ID with multiple formats."""
        patterns = [
            r'\b(ORD-\d+)\b',
            r'\border[:\s]+([A-Z0-9-]+)\b',
            r'\b([A-Z]{2,3}\d{6,})\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    async def _process_with_handler(
        self, 
        intent: IntentType, 
        message: str, 
        extracted_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Process message with the appropriate handler."""
        handler = self._handlers.get(intent)
        if not handler:
            logger.warning("No handler found for intent", intent=intent.value)
            handler = self._handlers[IntentType.FALLBACK]
        
        handler_context = {**context, **extracted_data, 'message': message}
        return await handler.handle(message, handler_context)

    async def _save_conversation_turn(
        self, conv_id: str, message: str, response: str, history: List[Dict]
    ) -> None:
        """Save conversation turn with error handling."""
        try:
            new_history = history.copy()
            new_history.extend([
                {"role": "user", "content": message, "timestamp": time.time()},
                {"role": "assistant", "content": response, "timestamp": time.time()}
            ])
            await self.conversation_manager.save_history(conv_id, new_history)
        except Exception as e:
            logger.error("Failed to save conversation turn", 
                        conv_id=conv_id, error=str(e))

# Handler Implementations

class GreetingHandler:
    """Handler for greeting intents."""
    
    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        history = context.get('history', [])
        if not history:
            return "Hello! I'm here to help you find products, check orders, or answer any questions. What can I do for you today?"
        
        user_turns = [turn for turn in history if turn.get('role') == 'user']
        if len(user_turns) > 1:
            return "Welcome back! How can I assist you today?"
        return "Nice to hear from you again! What would you like to explore?"

class ProductQueryHandler:
    """Handler for product query intents."""
    
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        keywords = context.get('keywords', [])
        filters = context.get('filters', {})
        
        if not keywords:
            return "I'd be happy to help you find products! Could you tell me what you're looking for?"

        try:
            products = await self._fetch_products(keywords, filters)
            if not products:
                return f"I couldn't find any products matching '{' '.join(keywords)}'. Try different keywords or browse our categories."
            
            return self._format_product_results(products, keywords)
            
        except Exception as e:
            logger.error("Product query failed", error=str(e), keywords=keywords)
            return "I'm having trouble searching for products right now. Please try again in a moment."

    async def _fetch_products(self, keywords: List[str], filters: Dict[str, Any]) -> List[Dict]:
        """Fetch products with enhanced parameters."""
        async def fetch():
            headers = {"Authorization": f"Bearer {self.processor.settings.INTERNAL_API_KEY}"}
            params = {
                "keywords": " ".join(keywords),
                "limit": self.processor.settings.MAX_PRODUCTS_TO_SHOW,
                **filters
            }
            
            timeout = httpx.Timeout(10.0, connect=5.0)
            response = await self.processor.http_client.get(
                self.processor.settings.ECOMMERCE_API_URL,
                headers=headers,
                params=params,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()

        return await self.processor.ecommerce_circuit_breaker.call(fetch)

    def _format_product_results(self, products: List[Dict], keywords: List[str]) -> str:
        """Format product results with enhanced presentation."""
        if len(products) == 1:
            product = products[0]
            return f"I found this product for you:\n\n🔹 **{product['title']}**\n💰 ${product['price']}\n📝 {product.get('description', 'No description available')[:100]}..."
        
        product_list = []
        for i, product in enumerate(products[:5], 1):  # Limit display
            availability = "✅ In Stock" if product.get('availability') != 'out_of_stock' else "❌ Out of Stock"
            product_list.append(f"{i}. **{product['title']}** - ${product['price']} ({availability})")
        
        result = f"I found {len(products)} products matching '{' '.join(keywords)}':\n\n"
        result += "\n".join(product_list)
        
        if len(products) > 5:
            result += f"\n\n... and {len(products) - 5} more. Ask me about any specific product for more details!"
        else:
            result += "\n\nWould you like more details about any of these products?"
        
        return result

class ProductDetailsHandler:
    """Handler for product details follow-up intents."""
    
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        product_title = context.get('product_title')
        if not product_title:
            return "Which product would you like to know more about? Please mention the product name."

        try:
            product = await self._fetch_product_details(product_title)
            if not product:
                return f"I couldn't find detailed information for '{product_title}'. Could you check the product name?"
            
            return self._format_product_details(product)
            
        except Exception as e:
            logger.error("Product details fetch failed", error=str(e), product=product_title)
            return f"I'm having trouble getting details for '{product_title}' right now. Please try again later."

    async def _fetch_product_details(self, product_title: str) -> Optional[Dict]:
        """Fetch detailed product information."""
        async def fetch():
            headers = {"Authorization": f"Bearer {self.processor.settings.INTERNAL_API_KEY}"}
            params = {"title": product_title}
            
            timeout = httpx.Timeout(10.0, connect=5.0)
            response = await self.processor.http_client.get(
                f"{self.processor.settings.ECOMMERCE_API_URL}/details",
                headers=headers,
                params=params,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()

        return await self.processor.ecommerce_circuit_breaker.call(fetch)

    def _format_product_details(self, product: Dict) -> str:
        """Format detailed product information."""
        details = [
            f"📦 **{product['title']}**",
            f"💰 **Price:** ${product['price']}",
        ]
        
        if product.get('description'):
            details.append(f"📝 **Description:** {product['description']}")
        
        if product.get('availability'):
            status = "✅ Available" if product['availability'] != 'out_of_stock' else "❌ Out of Stock"
            details.append(f"📊 **Availability:** {status}")
        
        if product.get('rating'):
            details.append(f"⭐ **Rating:** {product['rating']}/5")
        
        if product.get('reviews_count'):
            details.append(f"💬 **Reviews:** {product['reviews_count']} customer reviews")
        
        return "\n".join(details) + "\n\nWould you like to know anything else about this product?"

class OrderStatusHandler:
    """Handler for order status intents."""
    
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        order_id = context.get('order_id')
        if not order_id:
            return "Please provide your order ID (e.g., ORD-123456) to check the status."

        try:
            order = await self._fetch_order_status(order_id)
            return self._format_order_status(order)
            
        except Exception as e:
            logger.error("Order status fetch failed", error=str(e), order_id=order_id)
            return f"I couldn't retrieve the status for order {order_id}. Please verify the order ID and try again."

    async def _fetch_order_status(self, order_id: str) -> Dict:
        """Fetch order status information."""
        async def fetch():
            headers = {"Authorization": f"Bearer {self.processor.settings.INTERNAL_API_KEY}"}
            timeout = httpx.Timeout(10.0, connect=5.0)
            response = await self.processor.http_client.get(
                f"{self.processor.settings.ECOMMERCE_API_URL}/order/{order_id}",
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()

        return await self.processor.ecommerce_circuit_breaker.call(fetch)

    def _format_order_status(self, order: Dict) -> str:
        """Format order status information."""
        status_emoji = {
            'pending': '⏳',
            'processing': '🔄',
            'shipped': '🚚',
            'delivered': '✅',
            'cancelled': '❌'
        }
        
        status = order.get('status', 'unknown').lower()
        emoji = status_emoji.get(status, '📦')
        
        result = f"{emoji} **Order {order.get('id', 'N/A')}**\n"
        result += f"📋 **Status:** {status.title()}\n"
        
        if order.get('estimated_delivery'):
            result += f"📅 **Estimated Delivery:** {order['estimated_delivery']}\n"
        
        if order.get('tracking_number'):
            result += f"🔍 **Tracking:** {order['tracking_number']}\n"
        
        if order.get('items'):
            result += f"📦 **Items:** {len(order['items'])} item(s)\n"
        
        return result + "\nIs there anything else you'd like to know about your order?"

class FallbackHandler:
    """Handler for fallback intents using LLM."""
    
    def __init__(self, processor: 'AsyncAIProcessor'):
        self.processor = processor

    async def handle(self, message: str, context: Dict[str, Any]) -> str:
        # Try knowledge retrieval first
        if self.processor.knowledge_retriever:
            try:
                results = await self.processor.knowledge_retriever.search(message, limit=1)
                if results and results[0].get('chunk_text'):
                    return f"Based on your query: {results[0]['chunk_text']}"
            except Exception as e:
                logger.warning("Knowledge retrieval failed", error=str(e))
        
        # Fallback to LLM
        try:
            return await self._call_llm(message, context)
        except Exception as e:
            logger.error("LLM fallback failed", error=str(e))
            return "I'm having trouble understanding your request. Could you please rephrase it or try asking something else?"

    async def _call_llm(self, message: str, context: Dict[str, Any]) -> str:
        """Call LLM with enhanced context and error handling."""
        async def call_llm():
            # Build context-aware prompt
            history = context.get('history', [])
            conversation_context = self._build_conversation_context(history)
            
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{conversation_context}\n\nUser: {message}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 512,
                    "topP": 0.9,
                    "topK": 40
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
                ]
            }
            
            timeout = httpx.Timeout(20.0, connect=5.0)
            response = await self.processor.http_client.post(
                self.processor.api_url,
                headers=self.processor.headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            
            result = response.json()
            LLM_REQUEST_COUNT.labels(model='gemini-1.5-flash', status='success').inc()
            
            if 'candidates' not in result or not result['candidates']:
                raise AIServiceError("No response from LLM")
            
            return result['candidates'][0]['content']['parts'][0]['text']

        return await self.processor.llm_circuit_breaker.call(call_llm)

    def _build_conversation_context(self, history: List[Dict]) -> str:
        """Build conversation context for LLM."""
        if not history:
            return "You are a helpful AI assistant for an e-commerce platform."
        
        recent_turns = history[-4:]  # Last 4 turns for context
        context_parts = ["You are a helpful AI assistant for an e-commerce platform. Recent conversation:"]
        
        for turn in recent_turns:
            role = turn.get('role', '').title()
            content = turn.get('content', '')[:200]  # Limit length
            if role and content:
                context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)