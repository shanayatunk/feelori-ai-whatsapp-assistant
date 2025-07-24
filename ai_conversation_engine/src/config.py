# ai_conversation_engine/src/config.py
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional

class Settings(BaseSettings):
    """ Centralized, validated application configuration using Pydantic. """
    # --- API Keys & URLs ---
    GEMINI_API_KEY: Optional[str] = Field(None, env="GEMINI_API_KEY")
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    INTERNAL_API_KEY: str = Field(..., env="INTERNAL_API_KEY")
    ECOMMERCE_API_URL: str = Field(..., env="ECOMMERCE_API_URL")
    ALLOWED_ORIGINS: str = Field("*", env="ALLOWED_ORIGINS")

    # --- Redis Configuration ---
    REDIS_HOST: str = Field("redis", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(None, env="REDIS_PASSWORD")
    REDIS_SSL: bool = Field(False, env="REDIS_SSL")
    REDIS_MAX_CONNECTIONS: int = Field(50, ge=10)

    # --- HTTP Client Configuration ---
    HTTP_MAX_CONNECTIONS: int = Field(100, ge=10)
    HTTP_MAX_KEEPALIVE: int = Field(20, ge=5)
    REQUEST_TIMEOUT: float = Field(30.0, ge=1.0, le=120.0)

    # --- AI & Embedding Configuration ---
    GEMINI_MODEL: str = Field("gemini-2.5-flash-lite", env="GEMINI_MODEL")
    EMBEDDING_MODEL: str = Field("text-embedding-004", env="EMBEDDING_MODEL")
    EMBEDDING_DIMENSION: int = Field(768, ge=128, le=2048)
    EMBEDDING_MAX_RETRIES: int = Field(3, ge=1)
    EMBEDDING_RETRY_DELAY: float = Field(1.0, ge=0.5)
    EMBEDDING_TIMEOUT: float = Field(15.0, ge=5.0)
    EMBEDDING_BATCH_SIZE: int = Field(10, ge=1, le=100)
    MAX_MESSAGE_LENGTH: int = Field(4096, ge=256)
    MAX_PRODUCTS_TO_SHOW: int = Field(5, ge=1, le=20)
    SIMILARITY_THRESHOLD: float = Field(0.75, ge=0.0, le=1.0)


    # --- Application Logic ---
    CONVERSATION_TTL_SECONDS: int = Field(3600, ge=300)
    CACHE_TTL: int = Field(300, ge=60)
    CACHE_VERSION: str = Field("v1.0", env="CACHE_VERSION")
    MAX_CONCURRENT_REQUESTS: int = Field(50, ge=10)


    # --- Circuit Breaker Configuration ---
    LLM_FAILURE_THRESHOLD: int = Field(5, ge=1)
    LLM_RECOVERY_TIMEOUT: int = Field(60, ge=10)
    ECOMMERCE_FAILURE_THRESHOLD: int = Field(3, ge=1)
    ECOMMERCE_RECOVERY_TIMEOUT: int = Field(30, ge=10)

    # --- Rate Limiting ---
    RATE_LIMIT_REQUESTS: int = Field(100, ge=1)
    RATE_LIMIT_WINDOW: int = Field(60, ge=1)


    @validator('ECOMMERCE_API_URL')
    def validate_ecommerce_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('ECOMMERCE_API_URL must be a valid HTTP/HTTPS URL')
        return v

    @validator('ALLOWED_ORIGINS')
    def validate_allowed_origins(cls, v):
        if not v:
            raise ValueError("ALLOWED_ORIGINS cannot be empty. Use '*' for all or specify origins.")
        return v

    def validate_ai_keys(self):
        if not self.GEMINI_API_KEY and not self.OPENAI_API_KEY:
            raise ValueError("At least one AI service API key (GEMINI_API_KEY or OPENAI_API_KEY) must be provided.")

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        validate_assignment = True

settings = Settings()
settings.validate_ai_keys()