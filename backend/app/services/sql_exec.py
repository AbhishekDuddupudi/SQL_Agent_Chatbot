"""
Safe SQL execution with timeout and row cap.
"""
import time
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import get_engine
from app.core.config import get_settings


class SQLExecutionError(Exception):
    """Exception raised when SQL execution fails."""
    pass


def execute_query(
    sql: str,
    timeout_seconds: float = 30.0,
    row_cap: int = 200
) -> Tuple[List[str], List[Dict[str, Any]], int]:
    """
    Execute a SQL query safely with timeout and row cap.
    
    Args:
        sql: The SQL query to execute
        timeout_seconds: Maximum execution time
        row_cap: Maximum number of rows to return
        
    Returns:
        Tuple of (columns, rows_as_dicts, total_row_count)
        
    Raises:
        SQLExecutionError: If execution fails
    """
    settings = get_settings()
    effective_row_cap = min(row_cap, settings.max_limit)
    
    engine = get_engine()
    
    try:
        with engine.connect() as conn:
            # Set statement timeout for Postgres
            conn.execute(text(f"SET statement_timeout = '{int(timeout_seconds * 1000)}'"))
            
            # Execute the query
            result = conn.execute(text(sql))
            
            # Fetch results
            columns = list(result.keys())
            rows = result.fetchall()
            total_count = len(rows)
            
            # Cap rows if needed
            if total_count > effective_row_cap:
                rows = rows[:effective_row_cap]
            
            # Convert to list of dicts
            rows_as_dicts = [dict(zip(columns, row)) for row in rows]
            
            # Reset statement timeout
            conn.execute(text("SET statement_timeout = 0"))
            
            return columns, rows_as_dicts, total_count
            
    except SQLAlchemyError as e:
        error_msg = str(e)
        
        # Make error messages more user-friendly
        if "statement timeout" in error_msg.lower():
            raise SQLExecutionError("Query execution timed out. Try a more specific query.")
        elif "permission denied" in error_msg.lower():
            raise SQLExecutionError("Access denied for this query.")
        elif "does not exist" in error_msg.lower():
            raise SQLExecutionError(f"Database error: {error_msg}")
        else:
            raise SQLExecutionError(f"Query execution failed: {error_msg}")
    except Exception as e:
        raise SQLExecutionError(f"Unexpected error during query execution: {str(e)}")


def sanity_check_results(
    columns: List[str],
    rows: List[Dict[str, Any]],
    row_count: int
) -> Tuple[bool, Optional[str]]:
    """
    Perform sanity checks on query results.
    
    Args:
        columns: Column names
        rows: Result rows
        row_count: Total row count
        
    Returns:
        Tuple of (is_valid, warning_message)
    """
    warnings = []
    
    # Check for empty results
    if row_count == 0:
        return True, "Query returned no results."
    
    # Check for suspiciously large result sets
    if row_count > 10000:
        warnings.append(f"Very large result set ({row_count} rows). Consider adding filters.")
    
    # Check for potential null-heavy columns
    if rows:
        for col in columns:
            null_count = sum(1 for row in rows if row.get(col) is None)
            if null_count == len(rows):
                warnings.append(f"Column '{col}' contains only NULL values.")
    
    warning_msg = ' '.join(warnings) if warnings else None
    return True, warning_msg


def test_connection() -> bool:
    """
    Test database connectivity.
    
    Returns:
        True if connection is successful
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
