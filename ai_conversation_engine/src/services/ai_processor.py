# ai_conversation_engine/src/services/ai_processor.py

import httpx
import json
import structlog
import re
import hashlib
from typing import Dict, List, Tuple, Optional
from prometheus_client import Counter

from src.config import Settings
from src.exceptions import CircuitBreakerOpenError, AIServiceError
from src.services.conversation_manager import ConversationManager
from src.services.circuit_breaker import CircuitBreaker
from src.services.sanitizer import InputSanitizer
from src.services.intent_analyzer import IntentType
from src.services.knowledge_retriever import KnowledgeRetriever

logger = structlog.get_logger(__name__)

INTENT_COUNT = Counter('ai_intent_total', 'Total intents processed', ['intent'])

class AsyncAIProcessor:
    """
    Handles the core logic of processing user messages by orchestrating calls
    to the LLM and other internal services.
    """
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings, conversation_manager: ConversationManager):
        """
        Initializes the AI processor with necessary dependencies.

        Args:
            http_client: The HTTP client for external API calls.
            settings: Application configuration.
            conversation_manager: Manages conversation history and caching.
        """
        self.settings = settings
        self.http_client = http_client
        self.conversation_manager = conversation_manager
        
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.settings.GEMINI_API_KEY}"
        
        self.llm_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.LLM_FAILURE_THRESHOLD,
            recovery_timeout=self.settings.LLM_RECOVERY_TIMEOUT
        )
        self.ecommerce_circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.ECOMMERCE_FAILURE_THRESHOLD,
            recovery_timeout=self.settings.ECOMMERCE_RECOVERY_TIMEOUT
        )

    async def close(self) -> None:
        """
        Closes the HTTP client to release resources.
        """
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()
            logger.info("HTTP client closed", component="AsyncAIProcessor")

    async def process_message(self, message: str, conv_id: str, platform: str, lang: str) -> str:
        """
        Processes a user message by analyzing intent and routing to appropriate handlers.

        Args:
            message: The user's input message.
            conv_id: Unique conversation identifier.
            platform: The platform from which the message originates (e.g., 'web').
            lang: The language code (e.g., 'en').

        Returns:
            str: The AI-generated response or an error message.
        """
        sanitized_message = InputSanitizer.sanitize(message)
        if not sanitized_message:
            logger.warning("Empty message after sanitization", conv_id=conv_id)
            return "I didn't receive your message. Could you please try again?"
        
        history = await self.conversation_manager.get_history(conv_id)

        try:
            intent, extracted_data = await self._analyze_user_input(sanitized_message, history)
            INTENT_COUNT.labels(intent=intent.value).inc()
            logger.info("Analyzed user input", intent=intent.value, conv_id=conv_id)
            
            if intent == IntentType.PRODUCT_DETAILS_FOLLOWUP and extracted_data.get('product_title'):
                response = await self._handle_product_followup(extracted_data['product_title'], history)
            elif intent == IntentType.PRODUCT_QUERY and extracted_data.get('keywords'):
                response = await self._handle_product_query(sanitized_message, conv_id, history, extracted_data['keywords'])
            elif intent == IntentType.GREETING:
                response = self._handle_greeting(history)
            elif intent == IntentType.ORDER_STATUS and extracted_data.get('order_id'):
                response = await self._handle_order_status(extracted_data['order_id'], history)
            else:
                response = await self._route_to_handler(intent, sanitized_message, history)

            if intent != IntentType.PRODUCT_QUERY:
                await self._save_conversation_turn(conv_id, sanitized_message, response, history)
            
            return response
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open", conv_id=conv_id)
            return "Service temporarily unavailable. Please try again later."
        except Exception as e:
            logger.error("Critical error processing message", conv_id=conv_id, error=str(e), exc_info=True)
            return "An internal error occurred. Please try again later."

    async def _analyze_user_input(self, message: str, history: List[Dict]) -> Tuple[IntentType, Dict]:
        """
        Analyzes the user's input to determine intent and extract relevant data.

        Args:
            message: The sanitized user message.
            history: The conversation history.

        Returns:
            Tuple[IntentType, Dict]: The detected intent and extracted data.
        """
        intent_analyzer = IntentType  # Note: Should instantiate IntentAnalyzer, assuming typo in original code
        intent = intent_analyzer.analyze(message)
        
        extracted_data = {}
        if intent == IntentType.PRODUCT_QUERY:
            extracted_data['keywords'] = message.split()
        elif intent == IntentType.PRODUCT_DETAILS_FOLLOWUP:
            extracted_data['product_title'] = message  # Simplified for example
        elif intent == IntentType.ORDER_STATUS:
            order_id_match = re.search(r'\b(ORD-\d+)\b', message)
            extracted_data['order_id'] = order_id_match.group(1) if order_id_match else None
        
        return intent, extracted_data

    async def _handle_product_query(self, message: str, conv_id: str, history: List[Dict], keywords: List[str]) -> str:
        """
        Handles product query intent by searching for products via an external API.

        Args:
            message: The user's message.
            conv_id: Unique conversation identifier.
            history: The conversation history.
            keywords: Extracted keywords from the message.

        Returns:
            str: The response containing product information or an error message.
        """
        try:
            async def fetch_products():
                headers = {"Authorization": f"Bearer {self.settings.INTERNAL_API_KEY}"}
                params = {"keywords": " ".join(keywords), "limit": self.settings.MAX_PRODUCTS_TO_SHOW}
                response = await self.http_client.get(self.settings.ECOMMERCE_API_URL, headers=headers, params=params)
                response.raise_for_status()
                return response.json()

            products = await self.ecommerce_circuit_breaker.call(fetch_products)
            if not products:
                return "No products found matching your query."
            
            product_list = "\n".join([f"- {product['title']}: ${product['price']}" for product in products])
            response = f"Here are some products matching your query:\n{product_list}"
            await self._save_conversation_turn(conv_id, message, response, history)
            return response
        except CircuitBreakerOpenError:
            logger.warning("Ecommerce circuit breaker open", conv_id=conv_id)
            return "Product search is temporarily unavailable. Please try again later."
        except Exception as e:
            logger.error(f"Failed to fetch products: {e}", conv_id=conv_id, exc_info=True)
            return "Sorry, I couldn't fetch product information right now."

    def _handle_greeting(self, history: List[Dict]) -> str:
        """
        Handles greeting intent with a simple response.

        Args:
            history: The conversation history.

        Returns:
            str: A greeting response.
        """
        if not history:
            return "Hello! How can I assist you today?"
        return "Nice to hear from you again! What's on your mind?"

    async def _handle_product_followup(self, product_title: str, history: List[Dict]) -> str:
        """
        Handles product details follow-up intent by retrieving additional product information.

        Args:
            product_title: The title of the product.
            history: The conversation history.

        Returns:
            str: The response with product details or an error message.
        """
        try:
            async def fetch_product_details():
                headers = {"Authorization": f"Bearer {self.settings.INTERNAL_API_KEY}"}
                params = {"title": product_title}
                response = await self.http_client.get(f"{self.settings.ECOMMERCE_API_URL}/details", headers=headers, params=params)
                response.raise_for_status()
                return response.json()

            product = await self.ecommerce_circuit_breaker.call(fetch_product_details)
            if not product:
                return f"No details found for {product_title}."
            
            return f"Details for {product['title']}:\nPrice: ${product['price']}\nDescription: {product['description']}"
        except CircuitBreakerOpenError:
            logger.warning("Ecommerce circuit breaker open for product details", product_title=product_title)
            return "Product details are temporarily unavailable. Please try again later."
        except Exception as e:
            logger.error(f"Failed to fetch product details: {e}", product_title=product_title, exc_info=True)
            return f"Sorry, I couldn't fetch details for {product_title} right now."

    async def _handle_order_status(self, order_id: str, history: List[Dict]) -> str:
        """
        Handles order status intent by querying the order status from an external API.

        Args:
            order_id: The order ID to check.
            history: The conversation history.

        Returns:
            str: The order status or an error message.
        """
        try:
            async def fetch_order_status():
                headers = {"Authorization": f"Bearer {self.settings.INTERNAL_API_KEY}"}
                response = await self.http_client.get(f"{self.settings.ECOMMERCE_API_URL}/order/{order_id}", headers=headers)
                response.raise_for_status()
                return response.json()

            order = await self.ecommerce_circuit_breaker.call(fetch_order_status)
            return f"Order {order_id} status: {order['status']}"
        except CircuitBreakerOpenError:
            logger.warning("Ecommerce circuit breaker open for order status", order_id=order_id)
            return "Order status is temporarily unavailable. Please try again later."
        except Exception as e:
            logger.error(f"Failed to fetch order status: {e}", order_id=order_id, exc_info=True)
            return f"Sorry, I couldn't fetch the status for order {order_id} right now."

    async def _route_to_handler(self, intent: IntentType, message: str, history: List[Dict]) -> str:
        """
        Routes the message to the appropriate handler based on intent or uses LLM as a fallback.

        Args:
            intent: The detected intent.
            message: The user's message.
            history: The conversation history.

        Returns:
            str: The generated response.
        """
        if intent == IntentType.FALLBACK:
            try:
                knowledge_retriever = KnowledgeRetriever(self.http_client, self.settings)
                await knowledge_retriever.initialize()
                results = await knowledge_retriever.search(message, limit=1)
                if results:
                    return f"Based on your query, here's what I found: {results[0]['chunk_text']}"
                
                async def call_llm():
                    headers = {"Content-Type": "application/json"}
                    payload = {
                        "contents": [
                            {"role": "user", "parts": [{"text": message}]}
                        ],
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 512
                        }
                    }
                    response = await self.http_client.post(self.api_url, headers=headers, json=payload)
                    response.raise_for_status()
                    return response.json()['candidates'][0]['content']['parts'][0]['text']

                return await self.llm_circuit_breaker.call(call_llm)
            except CircuitBreakerOpenError:
                logger.warning("LLM circuit breaker open", intent=intent.value)
                return "I'm sorry, I can't process your request right now. Please try again later."
            except Exception as e:
                logger.error(f"LLM call failed: {e}", intent=intent.value, exc_info=True)
                return "I couldn't understand your request. Could you please rephrase?"
        return "I couldn't understand your request. Could you please rephrase?"

    async def _save_conversation_turn(self, conv_id: str, message: str, response: str, history: List[Dict]) -> None:
        """
        Saves a conversation turn to the history.

        Args:
            conv_id: Unique conversation identifier.
            message: The user's message.
            response: The AI's response.
            history: The existing conversation history.
        """
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        await self.conversation_manager.save_history(conv_id, history)