# shared/config.py
import os
from pathlib import Path
from pydantic_settings import BaseSettings
# MODIFIED: Import all necessary validators from Pydantic v2
from pydantic import Field, SecretStr, model_validator, field_validator
from typing import Optional, List

def read_secret_file(file_path_env: str) -> Optional[str]:
    """
    Read secret from file path specified in environment variable.
    Returns None if file doesn't exist or environment variable is not set.
    """
    file_path = os.getenv(file_path_env)
    if not file_path:
        return None
    
    try:
        secret_file = Path(file_path)
        if secret_file.exists():
            return secret_file.read_text().strip()
        else:
            print(f"Warning: Secret file {file_path} does not exist")
            return None
    except Exception as e:
        print(f"Error reading secret file {file_path}: {e}")
        return None

class Settings(BaseSettings):
    """Unified application configuration using Pydantic for all services."""

    # --- Secrets loaded from Docker Secrets ---
    GEMINI_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    INTERNAL_API_KEY: Optional[SecretStr] = None
    DATABASE_URL: Optional[SecretStr] = None
    WHATSAPP_ACCESS_TOKEN: Optional[SecretStr] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: Optional[SecretStr] = None
    WHATSAPP_WEBHOOK_SECRET: Optional[SecretStr] = None
    SHOPIFY_ACCESS_TOKEN: Optional[SecretStr] = None
    REDIS_PASSWORD: Optional[SecretStr] = None
    API_KEY: Optional[SecretStr] = None
    SECRET_KEY: Optional[SecretStr] = None
    
    # --- Non-Secret Configuration ---
    ECOMMERCE_API_URL: str = Field(..., env="ECOMMERCE_API_URL")
    ALLOWED_ORIGINS: str = Field("*", env="ALLOWED_ORIGINS")
    GEMINI_MODEL: str = Field("gemini-1.5-flash-latest", env="GEMINI_MODEL")
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
    CIRCUIT_BREAKER_FAIL_MAX: int = Field(5, env="CIRCUIT_BREAKER_FAIL_MAX")
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = Field(60, env="CIRCUIT_BREAKER_RESET_TIMEOUT")
    RATE_LIMIT_REQUESTS: int = Field(100, ge=1)
    RATE_LIMIT_WINDOW: int = Field(60, ge=1)
    HTTP_MAX_CONNECTIONS: int = Field(100, ge=10)
    HTTP_MAX_KEEPALIVE: int = Field(20, ge=5)
    REQUEST_TIMEOUT: float = Field(30.0, ge=1.0, le=120.0)
    REDIS_HOST: str = Field("redis", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_SSL: bool = Field(False, env="REDIS_SSL")
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    WHATSAPP_API_VERSION: str = Field("v17.0", env="WHATSAPP_API_VERSION")
    WHATSAPP_API_BASE_URL: str = Field("https://graph.facebook.com", env="WHATSAPP_API_BASE_URL")
    AI_SERVICE_TIMEOUT: int = Field(30, env="AI_SERVICE_TIMEOUT")
    REDIS_MAX_CONNECTIONS: int = Field(10, env="REDIS_MAX_CONNECTIONS")
    RATE_LIMIT_STORAGE_URL: Optional[str] = Field(None, env="RATE_LIMIT_STORAGE_URL")
    DEFAULT_RATE_LIMIT: str = Field("200 per minute", env="DEFAULT_RATE_LIMIT")
    WEBHOOK_RATE_LIMIT: str = Field("1000 per minute", env="WEBHOOK_RATE_LIMIT")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field("json", env="LOG_FORMAT")
    DEBUG: bool = Field(False, env="DEBUG")
    TESTING: bool = Field(False, env="TESTING")
    MAX_CONTENT_LENGTH: int = Field(1024 * 1024, env="MAX_CONTENT_LENGTH")
    METRICS_ENABLED: bool = Field(True, env="METRICS_ENABLED")
    HEALTH_CHECK_TIMEOUT: int = Field(5, env="HEALTH_CHECK_TIMEOUT")
    SUPPORTED_MESSAGE_TYPES: List[str] = Field(default=["text", "image", "audio", "document"], env="SUPPORTED_MESSAGE_TYPES")
    MESSAGE_RETRY_ATTEMPTS: int = Field(3, env="MESSAGE_RETRY_ATTEMPTS")
    MESSAGE_RETRY_DELAY: int = Field(5, env="MESSAGE_RETRY_DELAY")
    WEBHOOK_TIMEOUT: int = Field(10, env="WEBHOOK_TIMEOUT")
    WEBHOOK_MAX_RETRIES: int = Field(3, env="WEBHOOK_MAX_RETRIES")
    AI_SERVICE_URL: str = Field("http://ai-conversation-engine:5001", env="AI_SERVICE_URL")
    SHOPIFY_STORE_URL: str = Field(..., env="SHOPIFY_STORE_URL")
    
    def __init__(self, **kwargs):
        self._load_secrets_from_files()
        super().__init__(**kwargs)
    
    def _load_secrets_from_files(self):
        secret_mappings = {
            'GEMINI_API_KEY_FILE': 'GEMINI_API_KEY',
            'OPENAI_API_KEY_FILE': 'OPENAI_API_KEY',
            'INTERNAL_API_KEY_FILE': 'INTERNAL_API_KEY',
            'DATABASE_URL_FILE': 'DATABASE_URL',
            'WHATSAPP_ACCESS_TOKEN_FILE': 'WHATSAPP_ACCESS_TOKEN',
            'WHATSAPP_PHONE_NUMBER_ID_FILE': 'WHATSAPP_PHONE_NUMBER_ID',
            'WHATSAPP_VERIFY_TOKEN_FILE': 'WHATSAPP_VERIFY_TOKEN',
            'WHATSAPP_WEBHOOK_SECRET_FILE': 'WHATSAPP_WEBHOOK_SECRET',
            'SHOPIFY_ACCESS_TOKEN_FILE': 'SHOPIFY_ACCESS_TOKEN',
            'REDIS_PASSWORD_FILE': 'REDIS_PASSWORD',
            'API_KEY_FILE': 'API_KEY',
        }
        for file_env, secret_env in secret_mappings.items():
            secret_value = read_secret_file(file_env)
            if secret_value:
                os.environ[secret_env] = secret_value
                print(f"✅ Loaded {secret_env} from secret file")
            else:
                print(f"⚠️  Could not load {secret_env} from {file_env}")
        
        if not os.getenv('SECRET_KEY') and os.getenv('INTERNAL_API_KEY'):
            os.environ['SECRET_KEY'] = os.getenv('INTERNAL_API_KEY')
            print("✅ Set SECRET_KEY from INTERNAL_API_KEY")

    # --- Validators (UPDATED FOR PYDANTIC V2) ---

    @model_validator(mode='after')
    def build_redis_url(self) -> 'Settings':
        """Construct the Redis connection URL after loading other values."""
        if self.REDIS_URL:
            return self
        if self.REDIS_PASSWORD:
            password = self.REDIS_PASSWORD.get_secret_value()
            self.REDIS_URL = f"redis://:{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        else:
            self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        print("✅ Constructed REDIS_URL")
        return self

    # MODIFIED: Replaced @validator with @field_validator
    @field_validator('ECOMMERCE_API_URL')
    @classmethod
    def validate_ecommerce_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('ECOMMERCE_API_URL must be a valid HTTP/HTTPS URL')
        return v

    # MODIFIED: Replaced @validator with @field_validator
    @field_validator('ALLOWED_ORIGINS')
    @classmethod
    def validate_allowed_origins(cls, v):
        if not v:
            raise ValueError("ALLOWED_ORIGINS cannot be empty. Use '*' for all or specify origins.")
        if v == "*":
            return v
        origins = [origin.strip() for origin in v.split(',') if origin.strip()]
        return ','.join(origins)

    # MODIFIED: Replaced @validator with @field_validator
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v):
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'LOG_LEVEL must be one of: {allowed_levels}')
        return v.upper()

    # MODIFIED: Replaced @validator with @field_validator
    @field_validator('SUPPORTED_MESSAGE_TYPES')
    @classmethod
    def validate_message_types(cls, v):
        allowed_types = ["text", "image", "audio", "video", "document", "location", "contacts"]
        for msg_type in v:
            if msg_type not in allowed_types:
                raise ValueError(f'Unsupported message type: {msg_type}. Allowed: {allowed_types}')
        return v

    def validate_required_secrets(self):
        """Validate that required secrets are available."""
        required_secrets = [
            ('INTERNAL_API_KEY', self.INTERNAL_API_KEY),
            ('DATABASE_URL', self.DATABASE_URL),
            ('WHATSAPP_ACCESS_TOKEN', self.WHATSAPP_ACCESS_TOKEN),
            ('WHATSAPP_PHONE_NUMBER_ID', self.WHATSAPP_PHONE_NUMBER_ID),
            ('WHATSAPP_VERIFY_TOKEN', self.WHATSAPP_VERIFY_TOKEN),
        ]
        missing_secrets = [name for name, value in required_secrets if not value]
        if missing_secrets:
            raise ValueError(f"Missing required secrets: {', '.join(missing_secrets)}")

    def validate_ai_keys(self):
        """Validate that at least one AI service key is available."""
        if not self.GEMINI_API_KEY and not self.OPENAI_API_KEY:
            raise ValueError("At least one AI service API key (GEMINI_API_KEY or OPENAI_API_KEY) must be provided.")

    class Config:
        validate_assignment = True
        case_sensitive = True
        env_file = None

# Create settings instance
print("🔄 Initializing application settings...")
try:
    settings = Settings()
    settings.validate_required_secrets()
    settings.validate_ai_keys()
    print("✅ Settings initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize settings: {e}")
    raise