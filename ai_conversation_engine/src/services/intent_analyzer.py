# ai_conversation_engine/src/services/intent_analyzer.py

import re
import logging
from enum import Enum
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from rapidfuzz import fuzz, process
import asyncio

logger = logging.getLogger(__name__)

class IntentType(Enum):
    """Enumeration of supported intent types"""
    GREETING = "greeting"
    PRODUCT_QUERY = "product_query"
    PRODUCT_DETAILS_FOLLOWUP = "product_details_followup"
    ORDER_STATUS = "order_status"
    COMPLAINT = "complaint"
    SUPPORT_REQUEST = "support_request"
    PRICE_INQUIRY = "price_inquiry"
    AVAILABILITY_CHECK = "availability_check"
    GOODBYE = "goodbye"
    KNOWLEDGE_BASE_QUERY = "knowledge_base_query"  # <-- THIS IS THE CORRECTED LINE
    FALLBACK = "fallback"

@dataclass
class IntentResult:
    """Result of intent analysis"""
    intent: IntentType
    confidence: float
    matched_patterns: List[str]
    entities: Dict[str, str]

class IntentAnalyzer:
    """Advanced intent analyzer with multiple detection strategies"""
    
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        self.fallback_threshold = 70  # For fuzzy matching
        
        # Enhanced pattern matching with weighted keywords
        self.intent_patterns = {
            IntentType.GREETING: {
                "keywords": ["hello", "hi", "hey", "greetings", "good morning", 
                             "good afternoon", "good evening", "howdy", "sup"],
                "weight": 1.0
            },
            IntentType.PRODUCT_QUERY: {
                "keywords": ["find", "search", "product", "show me", "looking for", 
                             "need", "want", "buy", "purchase", "get me"],
                "weight": 1.2
            },
            IntentType.PRODUCT_DETAILS_FOLLOWUP: {
                "keywords": ["details", "more info", "tell me about", "specifications", 
                             "features", "description", "explain", "what is"],
                "weight": 1.1
            },
            IntentType.ORDER_STATUS: {
                "keywords": ["order status", "track order", "where is my order", 
                             "delivery status", "shipment", "tracking", "order update"],
                "weight": 1.3
            },
            IntentType.COMPLAINT: {
                "keywords": ["complaint", "problem", "issue", "wrong", "broken", 
                             "defective", "not working", "disappointed", "unhappy"],
                "weight": 1.2
            },
            IntentType.SUPPORT_REQUEST: {
                "keywords": ["help", "support", "assistance", "how to", "can you help", 
                             "need help", "guide me", "tutorial"],
                "weight": 1.0
            },
            IntentType.PRICE_INQUIRY: {
                "keywords": ["price", "cost", "how much", "expensive", "cheap", 
                             "discount", "offer", "deal", "rate"],
                "weight": 1.1
            },
            IntentType.AVAILABILITY_CHECK: {
                "keywords": ["available", "in stock", "out of stock", "when available", 
                             "do you have", "is it available"],
                "weight": 1.1
            },
            IntentType.GOODBYE: {
                "keywords": ["goodbye", "bye", "see you", "thanks", "thank you", 
                             "that's all", "done", "exit"],
                "weight": 1.0
            }
        }
        
        # Regular expressions for entity extraction
        self.entity_patterns = {
            "order_id": re.compile(r'\b(?:order|order[#\s]?(?:id|number)?[:\s#]*)?([A-Z0-9]{6,})\b', re.IGNORECASE),
            "product_name": re.compile(r'\b(?:product|item)[:\s]+([^.!?]+)', re.IGNORECASE),
            "phone_number": re.compile(r'\b(?:\+91|91)?[6-9]\d{9}\b'),
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        }
        
        # Context-aware modifiers
        self.context_modifiers = {
            "urgent": ["urgent", "asap", "immediately", "quickly", "fast"],
            "polite": ["please", "kindly", "could you", "would you"],
            "negative": ["not", "don't", "can't", "won't", "never"],
        }

    async def analyze(self, message: str, context: Optional[Dict] = None) -> IntentResult:
        """
        Analyzes the intent of a user message with enhanced detection.
        
        Args:
            message: User input message
            context: Optional conversation context
            
        Returns:
            IntentResult with detected intent and metadata
        """
        if not message or not message.strip():
            return IntentResult(
                intent=IntentType.FALLBACK,
                confidence=0.0,
                matched_patterns=[],
                entities={}
            )
        
        # Preprocess message
        processed_message = self._preprocess_message(message)
        
        # Extract entities
        entities = self._extract_entities(message)
        
        # Multiple detection strategies
        keyword_result = self._keyword_matching(processed_message)
        fuzzy_result = self._fuzzy_matching(processed_message)
        pattern_result = self._pattern_matching(processed_message)
        
        # Combine results with weighted scoring
        final_result = self._combine_results(
            [keyword_result, fuzzy_result, pattern_result],
            entities,
            context
        )
        
        logger.debug(f"Intent analysis for '{message[:50]}...': {final_result.intent.value} "
                     f"(confidence: {final_result.confidence:.2f})")
        
        return final_result

    def _preprocess_message(self, message: str) -> str:
        """Preprocesses the message for better analysis"""
        # Convert to lowercase and strip whitespace
        processed = message.lower().strip()
        
        # Remove extra whitespace
        processed = re.sub(r'\s+', ' ', processed)
        
        # Remove common punctuation that doesn't affect intent
        processed = re.sub(r'[^\w\s@#.-]', ' ', processed)
        
        return processed

    def _extract_entities(self, message: str) -> Dict[str, str]:
        """Extracts entities from the message using regex patterns"""
        entities = {}
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = pattern.findall(message)
            if matches:
                # Take the first match or join multiple matches
                entities[entity_type] = matches[0] if len(matches) == 1 else ', '.join(matches)
        
        return entities

    def _keyword_matching(self, message: str) -> Tuple[IntentType, float, List[str]]:
        """Performs exact keyword matching with scoring"""
        best_intent = IntentType.FALLBACK
        best_score = 0.0
        matched_patterns = []
        
        for intent, config in self.intent_patterns.items():
            keywords = config["keywords"]
            weight = config["weight"]
            matches = []
            
            for keyword in keywords:
                if keyword in message:
                    matches.append(keyword)
            
            if matches:
                # Score based on number of matches and keyword importance
                score = (len(matches) / len(keywords)) * weight
                if score > best_score:
                    best_score = score
                    best_intent = intent
                    matched_patterns = matches
        
        return best_intent, best_score, matched_patterns

    def _fuzzy_matching(self, message: str) -> Tuple[IntentType, float, List[str]]:
        """Performs fuzzy string matching"""
        best_intent = IntentType.FALLBACK
        best_score = 0.0
        matched_patterns = []
        
        for intent, config in self.intent_patterns.items():
            keywords = config["keywords"]
            weight = config["weight"]
            
            # Use process.extractOne for each keyword
            matches = []
            total_score = 0
            
            for keyword in keywords:
                match_result = process.extractOne(
                    keyword, 
                    [message], 
                    scorer=fuzz.partial_ratio
                )
                if match_result and match_result[1] > self.fallback_threshold:
                    matches.append(keyword)
                    total_score += match_result[1]
            
            if matches:
                # Average score weighted by intent importance
                avg_score = (total_score / len(matches)) / 100.0 * weight
                if avg_score > best_score:
                    best_score = avg_score
                    best_intent = intent
                    matched_patterns = matches
        
        return best_intent, best_score, matched_patterns

    def _pattern_matching(self, message: str) -> Tuple[IntentType, float, List[str]]:
        """Performs advanced pattern matching using heuristics"""
        patterns = []
        
        # Question patterns
        if message.startswith(('what', 'how', 'when', 'where', 'why', 'which')):
            if any(word in message for word in ['price', 'cost', 'much']):
                return IntentType.PRICE_INQUIRY, 0.8, ['question_price_pattern']
            elif any(word in message for word in ['available', 'stock']):
                return IntentType.AVAILABILITY_CHECK, 0.8, ['question_availability_pattern']
            else:
                return IntentType.SUPPORT_REQUEST, 0.7, ['question_pattern']
        
        # Order-related patterns
        if re.search(r'\border\s*(id|number)?\s*[:\s#]*[A-Z0-9]+', message, re.IGNORECASE):
            return IntentType.ORDER_STATUS, 0.9, ['order_id_pattern']
        
        # Greeting patterns
        if len(message.split()) <= 3 and any(greeting in message for greeting in ['hi', 'hello', 'hey']):
            return IntentType.GREETING, 0.9, ['short_greeting_pattern']
        
        return IntentType.FALLBACK, 0.0, []

    def _combine_results(
        self, 
        results: List[Tuple[IntentType, float, List[str]]], 
        entities: Dict[str, str],
        context: Optional[Dict] = None
    ) -> IntentResult:
        """Combines multiple detection results into final intent"""
        
        # Weight the results (keyword: 0.4, fuzzy: 0.3, pattern: 0.3)
        weights = [0.4, 0.3, 0.3]
        
        # Calculate weighted scores for each intent
        intent_scores = {}
        all_patterns = []
        
        for i, (intent, score, patterns) in enumerate(results):
            if intent != IntentType.FALLBACK:
                weighted_score = score * weights[i]
                if intent in intent_scores:
                    intent_scores[intent] += weighted_score
                else:
                    intent_scores[intent] = weighted_score
                all_patterns.extend(patterns)
        
        # Apply context modifiers
        if context:
            intent_scores = self._apply_context_modifiers(intent_scores, context)
        
        # Apply entity-based boosts
        intent_scores = self._apply_entity_boosts(intent_scores, entities)
        
        # Select best intent
        if intent_scores:
            best_intent = max(intent_scores.keys(), key=lambda x: intent_scores[x])
            confidence = min(1.0, intent_scores[best_intent])
            
            # Apply confidence threshold
            if confidence >= self.confidence_threshold:
                return IntentResult(
                    intent=best_intent,
                    confidence=confidence,
                    matched_patterns=list(set(all_patterns)),
                    entities=entities
                )
        
        return IntentResult(
            intent=IntentType.FALLBACK,
            confidence=0.0,
            matched_patterns=[],
            entities=entities
        )

    def _apply_context_modifiers(
        self, 
        intent_scores: Dict[IntentType, float], 
        context: Dict
    ) -> Dict[IntentType, float]:
        """Applies context-based score modifications"""
        modified_scores = intent_scores.copy()
        
        # Example: boost order status intent if previous message was about orders
        if context.get('last_intent') == IntentType.ORDER_STATUS:
            if IntentType.PRODUCT_DETAILS_FOLLOWUP in modified_scores:
                # Likely asking for order details, not product details
                modified_scores[IntentType.ORDER_STATUS] = modified_scores.get(
                    IntentType.ORDER_STATUS, 0
                ) + 0.2
        
        return modified_scores

    def _apply_entity_boosts(
        self, 
        intent_scores: Dict[IntentType, float], 
        entities: Dict[str, str]
    ) -> Dict[IntentType, float]:
        """Applies entity-based score boosts"""
        modified_scores = intent_scores.copy()
        
        # Boost order status if order ID is present
        if 'order_id' in entities:
            modified_scores[IntentType.ORDER_STATUS] = modified_scores.get(
                IntentType.ORDER_STATUS, 0
            ) + 0.3
        
        # Boost product query if product name is mentioned
        if 'product_name' in entities:
            modified_scores[IntentType.PRODUCT_QUERY] = modified_scores.get(
                IntentType.PRODUCT_QUERY, 0
            ) + 0.2
        
        return modified_scores

    def get_supported_intents(self) -> List[str]:
        """Returns list of supported intent types"""
        return [intent.value for intent in IntentType if intent != IntentType.FALLBACK]

    def update_patterns(self, intent: IntentType, new_keywords: List[str]) -> None:
        """Dynamically updates intent patterns"""
        if intent in self.intent_patterns:
            existing_keywords = set(self.intent_patterns[intent]["keywords"])
            updated_keywords = list(existing_keywords.union(set(new_keywords)))
            self.intent_patterns[intent]["keywords"] = updated_keywords
            logger.info(f"Updated patterns for {intent.value}: added {len(new_keywords)} keywords")
        else:
            logger.warning(f"Intent {intent.value} not found in patterns")

    async def batch_analyze(self, messages: List[str]) -> List[IntentResult]:
        """Analyzes multiple messages in batch"""
        tasks = [self.analyze(message) for message in messages]
        return await asyncio.gather(*tasks)