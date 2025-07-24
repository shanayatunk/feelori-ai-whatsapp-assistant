# ai_conversation_engine/src/routes/intent.py
import logging
from quart import Blueprint, request, jsonify, current_app
from pydantic import BaseModel, Field, ValidationError

from src.auth import require_api_key
from src.services.intent_analyzer import IntentResult
from src.exceptions import AIServiceError

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Blueprint ---
intent_bp = Blueprint('intent', __name__, url_prefix='/ai/v1/intent')

# --- Pydantic Models ---
class AnalyzeIntentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    context: dict = Field(default_factory=dict)

class AnalyzeIntentResponse(BaseModel):
    intent: str
    confidence: float
    matched_patterns: list[str]
    entities: dict[str, str]

# --- Routes ---
@intent_bp.route('/analyze', methods=['POST'])
@require_api_key
async def analyze_intent():
    """Analyzes the intent of a user message."""
    try:
        json_data = await request.get_json()
        validated_data = AnalyzeIntentRequest.model_validate(json_data)

        # Fix: Access intent_analyzer through the initialized ai_processor
        analyzer = current_app.ai_processor.intent_analyzer
        result: IntentResult = await analyzer.analyze(
            validated_data.message,
            validated_data.context
        )

        response = AnalyzeIntentResponse(
            intent=result.intent.value,
            confidence=result.confidence,
            matched_patterns=result.matched_patterns,
            entities=result.entities
        )

        return jsonify(response.model_dump()), 200

    except ValidationError as e:
        logger.warning("Invalid input for intent analysis", extra={"error": str(e)})
        # Return a 400 Bad Request for validation errors
        return jsonify({"error": "bad_request", "message": str(e)}), 400

    except Exception:
        logger.error("Unexpected error analyzing intent", exc_info=True)
        # Return a 500 Internal Server Error for other exceptions
        return jsonify({"error": "internal_server_error", "message": "An internal error occurred"}), 500