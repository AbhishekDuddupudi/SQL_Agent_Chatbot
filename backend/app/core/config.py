"""
Application configuration using Pydantic Settings
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://pharma_user:pharma_secret_123@localhost:5432/pharma_db"
    
    # Application
    app_name: str = "Pharma Analyst Bot"
    debug: bool = False
    
    # SQL Policy
    default_limit: int = 200
    max_limit: int = 200
    
    # LLM Settings
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout: float = 30.0
    llm_max_retries: int = 2
    
    # Query Execution
    query_timeout_seconds: float = 30.0
    max_row_cap: int = 200
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

