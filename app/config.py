"""Application configuration management."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    database_url: str = "postgresql://trading_user:password@localhost:5432/trading_data"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Broker
    broker: str = "kite"  # kite or fyers
    
    # Kite API
    kite_api_key: Optional[str] = None
    kite_api_secret: Optional[str] = None
    kite_username: Optional[str] = None
    kite_password: Optional[str] = None
    kite_totp_key: Optional[str] = None
    kite_access_token: Optional[str] = None
    
    # Fyers API
    fyers_app_id: Optional[str] = None
    fyers_access_token: Optional[str] = None
    
    # Application
    log_level: str = "INFO"
    tick_buffer_size: int = 1000
    flush_interval_seconds: int = 1
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

