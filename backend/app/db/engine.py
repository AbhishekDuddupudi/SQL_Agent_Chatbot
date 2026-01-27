"""
SQLAlchemy database engine configuration
"""
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings


@lru_cache()
def get_engine() -> Engine:
    """
    Get cached SQLAlchemy engine instance.
    Uses connection pooling for efficiency.
    """
    settings = get_settings()
    
    engine = create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Enable connection health checks
        echo=settings.debug  # Log SQL queries in debug mode
    )
    
    return engine


def get_connection():
    """Get a database connection from the pool."""
    engine = get_engine()
    return engine.connect()
