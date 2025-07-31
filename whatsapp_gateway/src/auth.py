# C:\AI_Assistant_Solution\whatsapp_gateway\src\auth.py

import hmac
import hashlib
from functools import wraps
from quart import request, jsonify, current_app
from shared.config import settings

def validate_whatsapp_webhook(f):
    """
    Decorator to validate the signature of incoming WhatsApp webhooks.
    """
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        # 1. Get the signature from the request header
        signature = request.headers.get('X-Hub-Signature-256')
        
        if not signature:
            current_app.logger.warning("Webhook validation failed: Missing X-Hub-Signature-256 header")
            return jsonify({'error': 'Unauthorized: Missing signature'}), 401

        # 2. Get the raw request body
        request_body = await request.get_data()

        # 3. Calculate the expected signature
        # The signature starts with 'sha256=', so we slice it off
        try:
            hash_method, received_hash = signature.split('=', 1)
            if hash_method != 'sha256':
                raise ValueError("Unsupported hash method")

            # The secret is a Pydantic SecretStr, so we get its value
            webhook_secret = settings.WHATSAPP_WEBHOOK_SECRET.get_secret_value().encode('utf-8')
            
            # Calculate HMAC-SHA256
            expected_hash = hmac.new(webhook_secret, request_body, hashlib.sha256).hexdigest()

        except (ValueError, AttributeError) as e:
            current_app.logger.error(f"Webhook signature calculation error: {e}")
            return jsonify({'error': 'Unauthorized: Invalid signature format'}), 401

        # 4. Compare the signatures securely
        if not hmac.compare_digest(received_hash, expected_hash):
            current_app.logger.warning("Webhook validation failed: Invalid signature")
            return jsonify({'error': 'Unauthorized: Invalid signature'}), 401

        # If validation is successful, proceed to the route handler
        return await f(*args, **kwargs)

    return decorated_function