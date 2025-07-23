# ai_conversation_engine/src/services/intent_analyzer.py

from enum import Enum
from typing import List, Dict
from rapidfuzz import fuzz  # ✅ Replaced fuzzywuzzy with rapidfuzz
import asyncio

class IntentType(Enum):
    GREETING = "greeting"
    PRODUCT_QUERY = "product_query"
    PRODUCT_DETAILS_FOLLOWUP = "product_details_followup"
    ORDER_STATUS = "order_status"
    FALLBACK = "fallback"

class IntentAnalyzer:
    def __init__(self):
        self.intent_patterns = {
            IntentType.GREETING: ["hello", "hi", "hey"],
            IntentType.PRODUCT_QUERY: ["find", "search", "product"],
            IntentType.PRODUCT_DETAILS_FOLLOWUP: ["details", "more info", "tell me about"],
            IntentType.ORDER_STATUS: ["order status", "track order"],
        }

    async def analyze(self, message: str) -> IntentType:
        """
        Analyzes the intent of a user message.

        Args:
            message: The user message to analyze.

        Returns:
            IntentType: The detected intent.
        """
        async def compute_score(intent, keywords):
            return max(fuzz.partial_ratio(message.lower(), kw) for kw in keywords)

        tasks = [compute_score(intent, keywords) for intent, keywords in self.intent_patterns.items()]
        scores = await asyncio.gather(*[asyncio.to_thread(compute_score, intent, keywords) for intent, keywords in self.intent_patterns.items()])
        intent_scores = dict(zip(self.intent_patterns.keys(), scores))
        return max(intent_scores.items(), key=lambda x: x[1])[0]