# tests/test_ai_processor.py
import pytest
from unittest.mock import patch, Mock
from src.services.ai_processor import AIProcessor

@pytest.fixture
def ai():
    return AIProcessor()

def test_greeting(ai):
    resp = ai.generate_response("hi", "greeting", {}, {}, "1")
    assert "help" in resp.lower()

def test_escalation(ai):
    resp = ai.generate_response("speak to agent", "escalation", {}, {}, "1")
    assert "human" in resp.lower()

@patch('src.services.ai_processor.requests.post')
def test_product_query(mock_post, ai):
    mock_post.return_value = Mock(status_code=200, json=lambda: {'products': [{"title": "Ring", "price_range": {"min": 99}}]})
    resp = ai.generate_response("ring", "product_query", {}, {}, "1")
    assert "ring" in resp.lower()

@patch('src.services.ai_processor.requests.get')
def test_order_status_query_found(mock_get, ai):
    mock_get.return_value = Mock(status_code=200, json=lambda: {'result': {"status": "shipped"}})
    resp = ai.generate_response("order 12345", "order_status", {}, {}, "1")
    assert "shipped" in resp.lower()

@patch('src.services.ai_processor.requests.get')
def test_order_status_query_not_found(mock_get, ai):
    mock_get.return_value = Mock(status_code=404)
    resp = ai.generate_response("order 12345", "order_status", {}, {}, "1")
    assert "not found" in resp.lower()

@patch('src.services.ai_processor.OpenAI.chat.completions.create')
def test_openai_429_retry(mock_create, ai):
    mock_create.side_effect = Exception("429 Too Many Requests")
    resp = ai._generate_general_response("hello", {})
    assert "trouble" in resp.lower() or "mock" in resp.lower()
