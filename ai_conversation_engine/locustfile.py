# ai_conversation_engine/locustfile.py

from locust import HttpUser, task, between

class AIConversationUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def process_message(self):
        self.client.post(
            "/ai/v1/process",
            json={
                "conv_id": "test12345678",
                "message": "Find me a laptop",
                "platform": "web",
                "lang": "en",
                "csrf_token": "valid-token"
            },
            headers={"X-API-Key": "test-key"}
        )