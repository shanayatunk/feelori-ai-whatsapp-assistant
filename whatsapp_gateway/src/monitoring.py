from prometheus_client import Counter, Histogram, generate_latest
import time
from flask import Response

# Metrics
message_counter = Counter('whatsapp_messages_total', 'Total messages processed', ['type', 'status'])
response_time = Histogram('whatsapp_response_time_seconds', 'Response time for WhatsApp API calls')
conversation_duration = Histogram('conversation_duration_seconds', 
                                 'Time from first to last message')
ai_response_time = Histogram('ai_service_response_seconds',
                           'AI service response time')
webhook_processing_time = Histogram('webhook_processing_seconds',
                                  'Webhook processing time')
error_counter = Counter('errors_total', 'Total errors', ['error_type', 'endpoint'])

def track_message(message_type, status):
    message_counter.labels(type=message_type, status=status).inc()

# Add to main.py for /metrics