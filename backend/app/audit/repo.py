"""
Audit logging repository
Handles inserting records into the audit_log table for every request.
"""
from typing import Optional
from sqlalchemy import text

from app.db.engine import get_engine


def insert_audit_log(
    session_id: str,
    question: str,
    sql_text: Optional[str],
    runtime_ms: int,
    row_count: int,
    error_text: Optional[str]
) -> None:
    """
    Insert an audit log entry for a chat request.
    
    Args:
        session_id: The session identifier
        question: The user's original question
        sql_text: The generated SQL query (if any)
        runtime_ms: Query execution time in milliseconds
        row_count: Number of rows returned
        error_text: Error message if any error occurred
    """
    engine = get_engine()
    
    insert_query = text("""
        INSERT INTO audit_log (session_id, question, sql_text, runtime_ms, row_count, error_text)
        VALUES (:session_id, :question, :sql_text, :runtime_ms, :row_count, :error_text)
    """)
    
    try:
        with engine.connect() as conn:
            conn.execute(
                insert_query,
                {
                    "session_id": session_id,
                    "question": question,
                    "sql_text": sql_text,
                    "runtime_ms": runtime_ms,
                    "row_count": row_count,
                    "error_text": error_text
                }
            )
            conn.commit()
    except Exception as e:
        # Log the error but don't fail the request
        print(f"Failed to insert audit log: {e}")


def get_audit_logs(session_id: Optional[str] = None, limit: int = 100):
    """
    Retrieve audit logs, optionally filtered by session_id.
    
    Args:
        session_id: Optional session ID to filter by
        limit: Maximum number of records to return
        
    Returns:
        List of audit log records
    """
    engine = get_engine()
    
    if session_id:
        query = text("""
            SELECT id, session_id, question, sql_text, runtime_ms, row_count, error_text, created_at
            FROM audit_log
            WHERE session_id = :session_id
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        params = {"session_id": session_id, "limit": limit}
    else:
        query = text("""
            SELECT id, session_id, question, sql_text, runtime_ms, row_count, error_text, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        params = {"limit": limit}
    
    with engine.connect() as conn:
        result = conn.execute(query, params)
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows]
