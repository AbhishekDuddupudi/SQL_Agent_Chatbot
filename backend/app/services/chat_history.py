"""
Chat session and message repository.
Handles persistence of chat sessions and message history.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import text

from app.db.engine import get_engine


def create_session(user_id: int) -> Dict[str, Any]:
    """
    Create a new chat session for a user.
    
    Returns:
        Session dict with id, user_id, title, created_at, updated_at
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                INSERT INTO chat_session (user_id)
                VALUES (:user_id)
                RETURNING id, user_id, title, created_at, updated_at
            """),
            {"user_id": user_id}
        )
        conn.commit()
        row = result.fetchone()
        
        return {
            "id": row[0],
            "user_id": row[1],
            "title": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "updated_at": row[4].isoformat() if row[4] else None
        }


def get_user_sessions(user_id: int) -> List[Dict[str, Any]]:
    """
    Get all sessions for a user, most recent first.
    
    Returns:
        List of session dicts
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT id, user_id, title, created_at, updated_at
                FROM chat_session
                WHERE user_id = :user_id
                ORDER BY updated_at DESC
            """),
            {"user_id": user_id}
        )
        
        sessions = []
        for row in result.fetchall():
            sessions.append({
                "id": row[0],
                "user_id": row[1],
                "title": row[2] or "New Chat",
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None
            })
        
        return sessions


def get_session(session_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Get a specific session.
    If user_id is provided, verifies ownership.
    
    Returns:
        Session dict or None if not found/not owned
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        if user_id is not None:
            result = conn.execute(
                text("""
                    SELECT id, user_id, title, created_at, updated_at
                    FROM chat_session
                    WHERE id = :session_id AND user_id = :user_id
                """),
                {"session_id": session_id, "user_id": user_id}
            )
        else:
            result = conn.execute(
                text("""
                    SELECT id, user_id, title, created_at, updated_at
                    FROM chat_session
                    WHERE id = :session_id
                """),
                {"session_id": session_id}
            )
        row = result.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "user_id": row[1],
            "title": row[2] or "New Chat",
            "created_at": row[3].isoformat() if row[3] else None,
            "updated_at": row[4].isoformat() if row[4] else None
        }


def get_session_messages(session_id: int, user_id: int) -> List[Dict[str, Any]]:
    """
    Get all messages for a session (verifies ownership).
    
    Returns:
        List of message dicts, ordered by created_at ASC
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        # First verify ownership
        ownership = conn.execute(
            text("SELECT 1 FROM chat_session WHERE id = :session_id AND user_id = :user_id"),
            {"session_id": session_id, "user_id": user_id}
        ).fetchone()
        
        if not ownership:
            return []
        
        result = conn.execute(
            text("""
                SELECT id, session_id, role, content, sql_query, created_at
                FROM chat_message
                WHERE session_id = :session_id
                ORDER BY created_at ASC
            """),
            {"session_id": session_id}
        )
        
        messages = []
        for row in result.fetchall():
            messages.append({
                "id": row[0],
                "session_id": row[1],
                "role": row[2],
                "content": row[3],
                "sql_query": row[4],
                "created_at": row[5].isoformat() if row[5] else None
            })
        
        return messages


def get_recent_messages(session_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent N messages for context (memory window).
    
    Returns:
        List of message dicts, ordered by created_at ASC (oldest first within window)
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        # Get recent messages in reverse order, then reverse again for chronological order
        result = conn.execute(
            text("""
                SELECT id, role, content, sql_query, created_at
                FROM chat_message
                WHERE session_id = :session_id
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"session_id": session_id, "limit": limit}
        )
        
        messages = []
        for row in result.fetchall():
            messages.append({
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "sql_query": row[3],
                "created_at": row[4].isoformat() if row[4] else None
            })
        
        # Reverse to get chronological order
        return list(reversed(messages))


def add_message(
    session_id: int,
    role: str,
    content: str,
    sql_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a message to a session and update session's updated_at.
    
    Args:
        session_id: The session to add to
        role: 'user' or 'assistant'
        content: The message content
        sql_query: Optional SQL (for assistant messages)
    
    Returns:
        The created message dict
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        # Insert message
        result = conn.execute(
            text("""
                INSERT INTO chat_message (session_id, role, content, sql_query)
                VALUES (:session_id, :role, :content, :sql_query)
                RETURNING id, session_id, role, content, sql_query, created_at
            """),
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "sql_query": sql_query
            }
        )
        row = result.fetchone()
        
        # Update session's updated_at
        conn.execute(
            text("UPDATE chat_session SET updated_at = NOW() WHERE id = :session_id"),
            {"session_id": session_id}
        )
        
        conn.commit()
        
        return {
            "id": row[0],
            "session_id": row[1],
            "role": row[2],
            "content": row[3],
            "sql_query": row[4],
            "created_at": row[5].isoformat() if row[5] else None
        }


def auto_title_session(session_id: int, first_message: str) -> str:
    """
    Auto-set session title from first user message.
    Takes first ~6-10 words, max 60 chars.
    
    Returns:
        The generated title
    """
    # Clean and truncate the message for title
    words = first_message.strip().split()
    title_words = words[:8]  # Take up to 8 words
    title = ' '.join(title_words)
    
    # Truncate to 60 chars
    if len(title) > 60:
        title = title[:57] + '...'
    elif len(words) > 8:
        title = title + '...'
    
    engine = get_engine()
    
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE chat_session 
                SET title = :title 
                WHERE id = :session_id AND title IS NULL
            """),
            {"session_id": session_id, "title": title}
        )
        conn.commit()
    
    return title


def should_auto_title(session_id: int) -> bool:
    """
    Check if a session needs auto-titling (has no title yet).
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT title FROM chat_session WHERE id = :session_id"),
            {"session_id": session_id}
        )
        row = result.fetchone()
        return row is not None and row[0] is None
