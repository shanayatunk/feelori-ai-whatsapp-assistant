# ai_conversation_engine/src/config.py

from pydantic import BaseSettings, Field, validator
from typing import Optional

class Settings(BaseSettings):
    """
    Centralized, validated application configuration using Pydantic.
    """
    GEMINI_API_KEY: Optional[str] = Field(None, env="GEMINI_API_KEY")
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    INTERNAL_API_KEY: str = Field(..., env="INTERNAL_API_KEY")
    ECOMMERCE_API_URL: str = Field(..., env="ECOMMERCE_API_URL")
    REDIS_HOST: str = Field("redis", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(None, env="REDIS_PASSWORD")
    REDIS_SSL: bool = Field(False, env="REDIS_SSL")
    REDIS_MAX_CONNECTIONS: int = Field(50, env="REDIS_MAX_CONNECTIONS", ge=10)  # ✅ Added
    HTTP_MAX_CONNECTIONS: int = Field(100, env="HTTP_MAX_CONNECTIONS", ge=10)  # ✅ Added
    HTTP_MAX_KEEPALIVE: int = Field(10, env="HTTP_MAX_KEEPALIVE", ge=5)  # ✅ Added
    EMBEDDING_DIMENSION: int = Field(768, env="EMBEDDING_DIMENSION", ge=128, le=2048)
    MAX_PRODUCTS_TO_SHOW: int = Field(5, ge=1, le=20)
    REQUEST_TIMEOUT: float = Field(30.0, ge=1.0, le=120.0)
    ALLOWED_ORIGINS: str = Field(..., env="ALLOWED_ORIGINS")
    CONVERSATION_TTL_SECONDS: int = Field(3600, ge=300)
    LLM_FAILURE_THRESHOLD: int = Field(5, ge=1)
    LLM_RECOVERY_TIMEOUT: int = Field(60, ge=10)
    ECOMMERCE_FAILURE_THRESHOLD: int = Field(3, ge=1)
    ECOMMERCE_RECOVERY_TIMEOUT: int = Field(30, ge=10)
    EMBEDDING_MODEL: str = Field("text-embedding-004", env="EMBEDDING_MODEL")
    RATE_LIMIT_REQUESTS: int = Field(20, ge=1)
    RATE_LIMIT_WINDOW: int = Field(60, ge=1)
    SIMILARITY_THRESHOLD: float = Field(0.75, ge=0.0, le=1.0)

    @validator('ECOMMERCE_API_URL')
    def validate_ecommerce_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('ECOMMERCE_API_URL must be a valid HTTP/HTTPS URL')
        return v

    @validator('ALLOWED_ORIGINS')
    def validate_allowed_origins(cls, v):
        if v == "*":
            raise ValueError("ALLOWED_ORIGINS must specify explicit origins, not '*'")
        return v

    @validator('CONVERSATION_TTL_SECONDS')
    def validate_ttl(cls, v):
        if v < 300:
            raise ValueError('TTL too low, minimum 300 seconds')
        return v

    def validate_ai_keys(self):
        if not self.GEMINI_API_KEY and not self.OPENAI_API_KEY:
            raise ValueError("At least one AI service API key must be provided.")

    class Config:
        env_file = ".env"
        validate_assignment = True

settings = Settings()
settings.validate_ai_keys()