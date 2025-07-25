# shared/config.py
from pydantic_settings import BaseSettings
from pydantic import Field, validator, SecretStr
from typing import Optional, List

class Settings(BaseSettings):
    """Unified application configuration using Pydantic for all services."""

    # --- AI-Specific Configuration (from ai_conversation_engine) ---
    GEMINI_API_KEY: Optional[SecretStr] = Field(None, env="GEMINI_API_KEY")
    OPENAI_API_KEY: Optional[SecretStr] = Field(None, env="OPENAI_API_KEY")
    INTERNAL_API_KEY: SecretStr = Field(..., env="INTERNAL_API_KEY")
    ECOMMERCE_API_URL: str = Field(..., env="ECOMMERCE_API_URL")
    ALLOWED_ORIGINS: str = Field("*", env="ALLOWED_ORIGINS")  # Standardized from CORS_ORIGINS
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
    CONVERSATION_TTL_SECONDS: int = Field(3600, ge=300)
    CACHE_TTL: int = Field(300, ge=60)
    CACHE_VERSION: str = Field("v1.0", env="CACHE_VERSION")
    MAX_CONCURRENT_REQUESTS: int = Field(50, ge=10)
    LLM_FAILURE_THRESHOLD: int = Field(5, ge=1)
    LLM_RECOVERY_TIMEOUT: int = Field(60, ge=10)
    ECOMMERCE_FAILURE_THRESHOLD: int = Field(3, ge=1)
    ECOMMERCE_RECOVERY_TIMEOUT: int = Field(30, ge=10)
    CIRCUIT_BREAKER_FAIL_MAX: int = Field(5, env="CIRCUIT_BREAKER_FAIL_MAX", description="Maximum failures before circuit breaker opens.")
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = Field(60, env="CIRCUIT_BREAKER_RESET_TIMEOUT", description="Time in seconds before the circuit breaker attempts to reset.") # <-- ADD THIS LINE
    RATE_LIMIT_REQUESTS: int = Field(100, ge=1)
    RATE_LIMIT_WINDOW: int = Field(60, ge=1)
    HTTP_MAX_CONNECTIONS: int = Field(100, ge=10)
    HTTP_MAX_KEEPALIVE: int = Field(20, ge=5)
    REQUEST_TIMEOUT: float = Field(30.0, ge=1.0, le=120.0)
    REDIS_HOST: str = Field("redis", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[SecretStr] = Field(None, env="REDIS_PASSWORD")
    REDIS_SSL: bool = Field(False, env="REDIS_SSL")
    REDIS_MAX_CONNECTIONS: int = Field(50, ge=10)
    REDIS_URL: str = Field("redis://redis:6379/0", env="REDIS_URL")  # Shared Redis URL

    # --- WhatsApp-Specific Configuration (from whatsapp_gateway) ---
    # FIXED: Updated DATABASE_URL to match docker-compose.yml postgres service
    DATABASE_URL: str = Field(
        default="postgresql://ai_assistant:ai_assistant_password@postgres:5432/ai_assistant",
        env="DATABASE_URL",
        description="PostgreSQL database connection URL"
    )
    WHATSAPP_ACCESS_TOKEN: SecretStr = Field(
        ..., env="WHATSAPP_ACCESS_TOKEN",
        description="WhatsApp Business API access token"
    )
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        ..., env="WHATSAPP_PHONE_NUMBER_ID",
        description="WhatsApp Business phone number ID"
    )
    WHATSAPP_VERIFY_TOKEN: str = Field(
        default="your_verify_token_here", env="WHATSAPP_VERIFY_TOKEN",
        description="WhatsApp webhook verification token"
    )
    WHATSAPP_WEBHOOK_SECRET: Optional[SecretStr] = Field(
        default=None, env="WHATSAPP_WEBHOOK_SECRET",
        description="WhatsApp webhook secret for signature verification"
    )
    WHATSAPP_API_VERSION: str = Field(
        default="v17.0", env="WHATSAPP_API_VERSION",
        description="WhatsApp Graph API version"
    )
    WHATSAPP_API_BASE_URL: str = Field(
        default="https://graph.facebook.com", env="WHATSAPP_API_BASE_URL",
        description="WhatsApp Graph API base URL"
    )
    AI_SERVICE_TIMEOUT: int = Field(
        default=30, env="AI_SERVICE_TIMEOUT",
        description="Timeout for AI service requests in seconds"
    )
    REDIS_MAX_CONNECTIONS: int = Field(  # Overlaps with AI, but consistent
        default=10, env="REDIS_MAX_CONNECTIONS",
        description="Maximum Redis connection pool size"
    )
    SECRET_KEY: SecretStr = Field(
        default="your-secret-key-change-in-production", env="SECRET_KEY",
        description="Flask secret key for session management"
    )
    API_KEY: Optional[SecretStr] = Field(
        default=None, env="API_KEY",
        description="API key for webhook authentication"
    )
    RATE_LIMIT_STORAGE_URL: Optional[str] = Field(
        default=None, env="RATE_LIMIT_STORAGE_URL",
        description="Storage backend for rate limiting (Redis URL)"
    )
    DEFAULT_RATE_LIMIT: str = Field(
        default="200 per minute", env="DEFAULT_RATE_LIMIT",
        description="Default rate limit for API endpoints"
    )
    WEBHOOK_RATE_LIMIT: str = Field(
        default="1000 per minute", env="WEBHOOK_RATE_LIMIT",
        description="Rate limit for webhook endpoints"
    )
    LOG_LEVEL: str = Field(
        default="INFO", env="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    LOG_FORMAT: str = Field(
        default="json", env="LOG_FORMAT",
        description="Log format (json or text)"
    )
    DEBUG: bool = Field(
        default=False, env="DEBUG",
        description="Enable debug mode"
    )
    TESTING: bool = Field(
        default=False, env="TESTING",
        description="Enable testing mode"
    )
    MAX_CONTENT_LENGTH: int = Field(
        default=1024 * 1024, env="MAX_CONTENT_LENGTH",  # 1MB
        description="Maximum request content length in bytes"
    )
    METRICS_ENABLED: bool = Field(
        default=True, env="METRICS_ENABLED",
        description="Enable Prometheus metrics collection"
    )
    HEALTH_CHECK_TIMEOUT: int = Field(
        default=5, env="HEALTH_CHECK_TIMEOUT",
        description="Health check timeout in seconds"
    )
    SUPPORTED_MESSAGE_TYPES: List[str] = Field(
        default=["text", "image", "audio", "document"], env="SUPPORTED_MESSAGE_TYPES",
        description="List of supported WhatsApp message types"
    )
    MESSAGE_RETRY_ATTEMPTS: int = Field(
        default=3, env="MESSAGE_RETRY_ATTEMPTS",
        description="Number of retry attempts for failed message processing"
    )
    MESSAGE_RETRY_DELAY: int = Field(
        default=5, env="MESSAGE_RETRY_DELAY",
        description="Delay between retry attempts in seconds"
    )
    WEBHOOK_TIMEOUT: int = Field(
        default=10, env="WEBHOOK_TIMEOUT",
        description="Webhook processing timeout in seconds"
    )
    WEBHOOK_MAX_RETRIES: int = Field(
        default=3, env="WEBHOOK_MAX_RETRIES",
        description="Maximum webhook retry attempts"
    )

    # --- Shared/Overlapping Configuration ---
    AI_SERVICE_URL: str = Field(
        default="http://ai-conversation-engine:5000", env="AI_SERVICE_URL",
        description="AI conversation engine service URL"
    )

    # --- Validators (Merged from both) ---
    @validator('ECOMMERCE_API_URL')
    def validate_ecommerce_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('ECOMMERCE_API_URL must be a valid HTTP/HTTPS URL')
        return v

    @validator('ALLOWED_ORIGINS')
    def validate_allowed_origins(cls, v):
        if not v:
            raise ValueError("ALLOWED_ORIGINS cannot be empty. Use '*' for all or specify origins.")
        if v == "*":
            return v
        # Split and clean up origins
        origins = [origin.strip() for origin in v.split(',') if origin.strip()]
        return ','.join(origins)

    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'LOG_LEVEL must be one of: {allowed_levels}')
        return v.upper()

    @validator('SUPPORTED_MESSAGE_TYPES')
    def validate_message_types(cls, v):
        allowed_types = ["text", "image", "audio", "video", "document", "location", "contacts"]
        for msg_type in v:
            if msg_type not in allowed_types:
                raise ValueError(f'Unsupported message type: {msg_type}. Allowed: {allowed_types}')
        return v

    def validate_ai_keys(self):
        if not self.GEMINI_API_KEY and not self.OPENAI_API_KEY:
            raise ValueError("At least one AI service API key (GEMINI_API_KEY or OPENAI_API_KEY) must be provided.")

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        validate_assignment = True
        case_sensitive = True  # From whatsapp

settings = Settings()
settings.validate_ai_keys()