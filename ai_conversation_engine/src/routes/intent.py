# ai_conversation_engine/src/routes/intent.py
from quart import Blueprint, jsonify, request
from src.services.intent_analyzer import IntentAnalyzer

intent_bp = Blueprint('intent', __name__, url_prefix='/ai')
intent_analyzer = IntentAnalyzer()

@intent_bp.route('/intent/analyze', methods=['POST'])
async def analyze_message_intent():
    """
    Analyzes the intent of a user message.

    Returns:
        JSON response with intent analysis or error.
    """
    try:
        data = await request.get_json()
        message = data.get('message')

        if not message:
            return jsonify({'error': 'message is required'}), 400

        intent_result = intent_analyzer.analyze_intent(message)
        return jsonify({'success': True, 'intent': intent_result}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500