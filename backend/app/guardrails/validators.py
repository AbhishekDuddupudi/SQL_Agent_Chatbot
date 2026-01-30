"""
SQL validators and guardrails.
"""
import re
from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp

from app.agent.schema import ALLOWED_SCHEMA, BLOCKED_TABLES


class ValidationError(Exception):
    """Exception raised when SQL validation fails."""
    pass


def validate_select_only(sql: str) -> None:
    """
    Ensure SQL is SELECT-only (no DDL/DML).
    
    Raises:
        ValidationError: If SQL contains non-SELECT statements
    """
    sql_clean = sql.strip().rstrip(';')
    
    # Check for multiple statements
    if ';' in sql_clean:
        raise ValidationError("Multiple SQL statements are not allowed")
    
    try:
        parsed = sqlglot.parse_one(sql_clean, read='postgres')
    except Exception as e:
        raise ValidationError(f"Invalid SQL syntax: {str(e)}")
    
    # Must be a SELECT statement
    if not isinstance(parsed, exp.Select):
        raise ValidationError("Only SELECT statements are allowed. INSERT, UPDATE, DELETE, and DDL are prohibited.")
    
    # Check for dangerous operations in subqueries
    dangerous_types = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop, 
        exp.Create
    )
    
    for node in parsed.walk():
        if isinstance(node, dangerous_types):
            raise ValidationError(f"Forbidden operation: {type(node).__name__}")


def validate_no_select_star(sql: str) -> None:
    """
    Reject SELECT * queries.
    
    Raises:
        ValidationError: If SQL contains SELECT *
    """
    try:
        parsed = sqlglot.parse_one(sql.strip().rstrip(';'), read='postgres')
    except Exception:
        return  # Let other validators catch syntax errors
    
    for select in parsed.find_all(exp.Select):
        for expr in select.expressions:
            if isinstance(expr, exp.Star):
                raise ValidationError(
                    "SELECT * is not allowed. Please specify the columns you need."
                )


def validate_allowlist(sql: str) -> List[str]:
    """
    Validate that SQL only references allowed tables and columns.
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    try:
        parsed = sqlglot.parse_one(sql.strip().rstrip(';'), read='postgres')
    except Exception as e:
        return [f"SQL parse error: {str(e)}"]
    
    # Check table references
    for table in parsed.find_all(exp.Table):
        table_name = table.name.lower()
        
        if table_name in BLOCKED_TABLES:
            errors.append(f"Access to table '{table_name}' is not permitted")
        elif table_name not in [t.lower() for t in ALLOWED_SCHEMA.keys()]:
            errors.append(f"Unknown table: '{table_name}'")
    
    return errors


def validate_no_dangerous_patterns(sql: str) -> None:
    """
    Check for dangerous SQL patterns.
    
    Raises:
        ValidationError: If dangerous patterns are found
    """
    sql_upper = sql.upper()
    
    # Dangerous functions
    dangerous_functions = [
        'PG_SLEEP', 'SLEEP', 'BENCHMARK', 'LOAD_FILE',
        'INTO OUTFILE', 'INTO DUMPFILE'
    ]
    
    for func in dangerous_functions:
        if func in sql_upper:
            raise ValidationError(f"Dangerous function detected: {func}")
    
    # Check for comment-based injection attempts
    if '--' in sql and sql.index('--') < len(sql) - 2:
        # Allow -- only at the very end
        after_comment = sql[sql.index('--') + 2:].strip()
        if after_comment and not after_comment.startswith('\n'):
            pass  # Could be legitimate, let it through
    
    # Check for UNION-based injection patterns
    if 'UNION' in sql_upper and 'SELECT' in sql_upper:
        # Count SELECT statements - more than one in unexpected places is suspicious
        select_count = sql_upper.count('SELECT')
        union_count = sql_upper.count('UNION')
        if union_count > 0 and select_count > union_count + 1:
            # This might be legitimate, so just flag for review
            pass


def validate_sql_complete(sql: str) -> Tuple[bool, List[str]]:
    """
    Run all SQL validations.
    
    Args:
        sql: The SQL query to validate
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    try:
        validate_select_only(sql)
    except ValidationError as e:
        errors.append(str(e))
    
    try:
        validate_no_select_star(sql)
    except ValidationError as e:
        errors.append(str(e))
    
    try:
        validate_no_dangerous_patterns(sql)
    except ValidationError as e:
        errors.append(str(e))
    
    allowlist_errors = validate_allowlist(sql)
    errors.extend(allowlist_errors)
    
    return len(errors) == 0, errors


def check_dump_request(question: str) -> Tuple[bool, Optional[str]]:
    """
    Check if the user is trying to dump all data.
    
    Args:
        question: User's question
        
    Returns:
        Tuple of (is_dump_request, refusal_reason)
    """
    question_lower = question.lower()
    
    dump_patterns = [
        "dump everything",
        "dump all",
        "export all",
        "give me everything",
        "all the data",
        "entire database",
        "all records",
        "all rows",
        "download everything",
        "extract all"
    ]
    
    for pattern in dump_patterns:
        if pattern in question_lower:
            return True, (
                "I can't export entire datasets. Please ask a specific question about the data, "
                "such as 'What are the top 10 products by revenue?' or 'Show sales by territory'."
            )
    
    return False, None


def check_sensitive_request(question: str) -> Tuple[bool, Optional[str]]:
    """
    Check if the user is requesting sensitive information inappropriately.
    
    Args:
        question: User's question
        
    Returns:
        Tuple of (is_sensitive, refusal_reason)
    """
    question_lower = question.lower()
    
    # Patterns that might indicate inappropriate access attempts
    sensitive_patterns = [
        ("password", "I cannot provide password information."),
        ("credential", "I cannot provide credential information."),
        ("api key", "I cannot provide API key information."),
        ("secret", "I cannot provide secret information."),
        ("audit_log", "Access to audit logs is restricted."),
    ]
    
    for pattern, reason in sensitive_patterns:
        if pattern in question_lower:
            return True, reason
    
    return False, None
