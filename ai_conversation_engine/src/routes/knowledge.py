# ai_conversation_engine/src/routes/knowledge.py
from flask import Blueprint, jsonify

knowledge_bp = Blueprint('knowledge', __name__)

@knowledge_bp.route('/knowledge/<path:u_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def knowledge_routes(u_path):
    # This functionality is now centralized in the main whatsapp-gateway service.
    return jsonify({
        "message": "This endpoint is deprecated. Knowledge base management is handled by the main gateway service."
    }), 410 # 410 Gone