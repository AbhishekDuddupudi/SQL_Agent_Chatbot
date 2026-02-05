"""
Authentication service for user login/logout.
Simple session-based auth for the POC.
"""
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
from sqlalchemy import text

from app.db.engine import get_engine

logger = logging.getLogger(__name__)

# Session duration (7 days for demo purposes)
SESSION_DURATION_DAYS = 7


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def get_user_by_email(email: str) -> Optional[dict]:
    """
    Look up a user by email address.
    
    Returns:
        User dict with id, email, password_hash, display_name, or None if not found.
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, email, password_hash, display_name FROM app_user WHERE email = :email"),
            {"email": email.lower().strip()}
        )
        row = result.fetchone()
        
        if row:
            return {
                "id": row[0],
                "email": row[1],
                "password_hash": row[2],
                "display_name": row[3]
            }
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    Look up a user by ID.
    
    Returns:
        User dict with id, email, display_name, or None if not found.
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, email, display_name FROM app_user WHERE id = :user_id"),
            {"user_id": user_id}
        )
        row = result.fetchone()
        
        if row:
            return {
                "id": row[0],
                "email": row[1],
                "display_name": row[2]
            }
        return None


def authenticate_user(email: str, password: str) -> Tuple[bool, Optional[dict], str]:
    """
    Authenticate a user with email and password.
    
    Returns:
        Tuple of (success, user_dict, error_message)
    """
    user = get_user_by_email(email)
    
    if not user:
        return False, None, "Invalid email or password"
    
    if not verify_password(password, user["password_hash"]):
        return False, None, "Invalid email or password"
    
    # Don't return password_hash to caller
    return True, {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"]
    }, ""


def create_session(user_id: int) -> str:
    """
    Create a new session for a user.
    
    Returns:
        Session ID (token) to be stored in cookie.
    """
    engine = get_engine()
    
    # Generate a secure random session ID
    session_id = secrets.token_hex(32)  # 64 character hex string
    expires_at = datetime.utcnow() + timedelta(days=SESSION_DURATION_DAYS)
    
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO user_session (id, user_id, expires_at)
                VALUES (:session_id, :user_id, :expires_at)
            """),
            {
                "session_id": session_id,
                "user_id": user_id,
                "expires_at": expires_at
            }
        )
        conn.commit()
    
    logger.info(f"Created session for user_id={user_id}")
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    """
    Look up a session by ID.
    
    Returns:
        Session dict with user_id, expires_at, or None if not found/expired.
    """
    if not session_id:
        return None
        
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT user_id, expires_at 
                FROM user_session 
                WHERE id = :session_id AND expires_at > NOW()
            """),
            {"session_id": session_id}
        )
        row = result.fetchone()
        
        if row:
            return {
                "user_id": row[0],
                "expires_at": row[1]
            }
        return None


def delete_session(session_id: str) -> bool:
    """
    Delete a session (logout).
    
    Returns:
        True if session was deleted, False if not found.
    """
    if not session_id:
        return False
        
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM user_session WHERE id = :session_id"),
            {"session_id": session_id}
        )
        conn.commit()
        
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted session {session_id[:8]}...")
        return deleted


def cleanup_expired_sessions() -> int:
    """
    Remove all expired sessions from the database.
    
    Returns:
        Number of sessions deleted.
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM user_session WHERE expires_at < NOW()")
        )
        conn.commit()
        
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
        return count
