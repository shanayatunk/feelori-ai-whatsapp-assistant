# whatsapp_gateway/src/config.py

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings using Pydantic for validation and type safety.
    All settings can be overridden via environment variables.
    """
    
    # --- Database Configuration ---
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@postgres:5432/ai_assistant",
        description="PostgreSQL database connection URL"
    )
    
    # --- WhatsApp API Configuration ---
    WHATSAPP_ACCESS_TOKEN: str = Field(
        ...,  # Required field
        description="WhatsApp Business API access token"
    )
    
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        ...,  # Required field
        description="WhatsApp Business phone number ID"
    )
    
    WHATSAPP_VERIFY_TOKEN: str = Field(
        default="your_verify_token_here",
        description="WhatsApp webhook verification token"
    )
    
    WHATSAPP_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="WhatsApp webhook secret for signature verification"
    )
    
    WHATSAPP_API_VERSION: str = Field(
        default="v17.0",
        description="WhatsApp Graph API version"
    )
    
    WHATSAPP_API_BASE_URL: str = Field(
        default="https://graph.facebook.com",
        description="WhatsApp Graph API base URL"
    )
    
    # --- AI Service Configuration ---
    AI_SERVICE_URL: str = Field(
        default="http://ai-conversation-engine:5000",
        description="AI conversation engine service URL"
    )
    
    AI_SERVICE_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for AI service authentication"
    )
    
    AI_SERVICE_TIMEOUT: int = Field(
        default=30,
        description="Timeout for AI service requests in seconds"
    )
    
    # --- Redis Configuration ---
    REDIS_URL: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL for caching and rate limiting"
    )
    
    REDIS_MAX_CONNECTIONS: int = Field(
        default=10,
        description="Maximum Redis connection pool size"
    )
    
    # --- Security Configuration ---
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="Flask secret key for session management"
    )
    
    API_KEY: Optional[str] = Field(
        default=None,
        description="API key for webhook authentication"
    )
    
    # --- CORS Configuration ---
    CORS_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # --- Rate Limiting ---
    RATE_LIMIT_STORAGE_URL: Optional[str] = Field(
        default=None,
        description="Storage backend for rate limiting (Redis URL)"
    )
    
    DEFAULT_RATE_LIMIT: str = Field(
        default="200 per minute",
        description="Default rate limit for API endpoints"
    )
    
    WEBHOOK_RATE_LIMIT: str = Field(
        default="1000 per minute",
        description="Rate limit for webhook endpoints"
    )
    
    # --- Logging Configuration ---
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    LOG_FORMAT: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    
    # --- Application Configuration ---
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    TESTING: bool = Field(
        default=False,
        description="Enable testing mode"
    )
    
    MAX_CONTENT_LENGTH: int = Field(
        default=1024 * 1024,  # 1MB
        description="Maximum request content length in bytes"
    )
    
    # --- Monitoring Configuration ---
    METRICS_ENABLED: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection"
    )
    
    HEALTH_CHECK_TIMEOUT: int = Field(
        default=5,
        description="Health check timeout in seconds"
    )
    
    # --- Message Processing ---
    MAX_MESSAGE_LENGTH: int = Field(
        default=4096,
        description="Maximum message length to process"
    )
    
    SUPPORTED_MESSAGE_TYPES: List[str] = Field(
        default=["text", "image", "audio", "document"],
        description="List of supported WhatsApp message types"
    )
    
    MESSAGE_RETRY_ATTEMPTS: int = Field(
        default=3,
        description="Number of retry attempts for failed message processing"
    )
    
    MESSAGE_RETRY_DELAY: int = Field(
        default=5,
        description="Delay between retry attempts in seconds"
    )
    
    # --- Webhook Configuration ---
    WEBHOOK_TIMEOUT: int = Field(
        default=10,
        description="Webhook processing timeout in seconds"
    )
    
    WEBHOOK_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum webhook retry attempts"
    )
    
    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        """Validate log level is one of the allowed values."""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'LOG_LEVEL must be one of: {allowed_levels}')
        return v.upper()
    
    @validator('CORS_ORIGINS')
    def validate_cors_origins(cls, v):
        """Ensure CORS origins is properly formatted."""
        if v == "*":
            return v
        # Split and clean up origins
        origins = [origin.strip() for origin in v.split(',') if origin.strip()]
        return ','.join(origins)
    
    @validator('SUPPORTED_MESSAGE_TYPES')
    def validate_message_types(cls, v):
        """Validate supported message types."""
        allowed_types = ["text", "image", "audio", "video", "document", "location", "contacts"]
        for msg_type in v:
            if msg_type not in allowed_types:
                raise ValueError(f'Unsupported message type: {msg_type}. Allowed: {allowed_types}')
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Allow environment variables to override settings
        # E.g., WHATSAPP_ACCESS_TOKEN env var will override whatsapp_access_token
        env_prefix = ""


# Create a global settings instance
settings = Settings()


def get_database_url() -> str:
    """
    Get the database URL with proper formatting.
    
    Returns:
        str: Formatted database URL
    """
    return settings.DATABASE_URL


def get_whatsapp_api_url() -> str:
    """
    Get the complete WhatsApp API URL.
    
    Returns:
        str: Complete WhatsApp API URL
    """
    return f"{settings.WHATSAPP_API_BASE_URL}/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}"


def is_production() -> bool:
    """
    Check if the application is running in production mode.
    
    Returns:
        bool: True if in production, False otherwise
    """
    return not settings.DEBUG and not settings.TESTING


def get_rate_limit_storage_url() -> str:
    """
    Get the rate limit storage URL, defaulting to Redis URL if not specified.
    
    Returns:
        str: Rate limit storage URL
    """
    return settings.RATE_LIMIT_STORAGE_URL or settings.REDIS_URL