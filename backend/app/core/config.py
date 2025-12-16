"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings."""
    
    # App
    APP_NAME: str = "API Test Generation Platform"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql://apitest:apitest123@localhost:5432/apitest_db"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Encryption
    ENCRYPTION_KEY: str = "your-encryption-key-change-in-production"
    
    # LLM Defaults
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4"
    LLM_API_KEY: str = ""  # LLM API key from environment variable
    
    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Monitoring
    SENTRY_DSN: str = ""
    ENABLE_METRICS: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

