"""
SQL Policy Guardrails using sqlglot
Enforces safety rules on SQL queries before execution.
"""
import sqlglot
from sqlglot import exp
from typing import Optional

from app.core.config import get_settings


class SQLPolicyError(Exception):
    """Exception raised when SQL violates policy rules."""
    pass


def validate_sql(sql: str) -> str:
    """
    Validate and potentially modify SQL to comply with security policies.
    
    Rules:
    1. Single statement only (no semicolon-separated statements)
    2. SELECT statements only (no DDL/DML: INSERT, UPDATE, DELETE, DROP, etc.)
    3. Enforce LIMIT: default 200 if missing, cap at 200 if higher
    4. Reject non-integer LIMIT values
    
    Args:
        sql: The SQL query to validate
        
    Returns:
        The validated (and possibly modified) SQL query
        
    Raises:
        SQLPolicyError: If the SQL violates any policy rules
    """
    settings = get_settings()
    default_limit = settings.default_limit
    max_limit = settings.max_limit
    
    # Strip whitespace and trailing semicolons
    sql = sql.strip().rstrip(';')
    
    # Check for multiple statements (simple check for semicolons in the middle)
    if ';' in sql:
        raise SQLPolicyError("Multiple SQL statements are not allowed. Please submit one query at a time.")
    
    # Parse the SQL
    try:
        parsed = sqlglot.parse_one(sql, read='postgres')
    except Exception as e:
        raise SQLPolicyError(f"Invalid SQL syntax: {str(e)}")
    
    # Check statement type - must be SELECT only
    if not isinstance(parsed, exp.Select):
        # Check for subquery wrapper
        if isinstance(parsed, exp.Subquery):
            inner = parsed.this
            if not isinstance(inner, exp.Select):
                raise SQLPolicyError("Only SELECT statements are allowed. DDL and DML operations (INSERT, UPDATE, DELETE, DROP, etc.) are prohibited.")
        else:
            raise SQLPolicyError("Only SELECT statements are allowed. DDL and DML operations (INSERT, UPDATE, DELETE, DROP, etc.) are prohibited.")
    
    # Check for dangerous operations within the SELECT
    _check_for_dangerous_operations(parsed)
    
    # Handle LIMIT clause
    parsed = _enforce_limit(parsed, default_limit, max_limit)
    
    # Generate the validated SQL
    validated_sql = parsed.sql(dialect='postgres')
    
    return validated_sql


def _check_for_dangerous_operations(parsed: exp.Expression) -> None:
    """
    Check for dangerous operations within the query.
    
    Raises:
        SQLPolicyError: If dangerous operations are found
    """
    # List of forbidden expression types
    forbidden_types = (
        exp.Insert,
        exp.Update, 
        exp.Delete,
        exp.Drop,
        exp.Create,
    )
    
    # Walk the entire expression tree
    for node in parsed.walk():
        if isinstance(node, forbidden_types):
            raise SQLPolicyError(
                f"Forbidden operation detected: {type(node).__name__}. "
                "Only SELECT queries are allowed."
            )
        
        # Check for dangerous functions
        if isinstance(node, exp.Anonymous):
            func_name = node.name.upper() if node.name else ""
            dangerous_functions = [
                'PG_SLEEP', 'SLEEP', 'BENCHMARK', 'LOAD_FILE', 
                'INTO OUTFILE', 'INTO DUMPFILE', 'EXEC', 'EXECUTE'
            ]
            if func_name in dangerous_functions:
                raise SQLPolicyError(f"Forbidden function: {func_name}")


def _enforce_limit(parsed: exp.Expression, default_limit: int, max_limit: int) -> exp.Expression:
    """
    Enforce LIMIT clause rules:
    - Add default LIMIT if missing
    - Cap LIMIT if exceeds maximum
    - Reject non-integer LIMIT
    
    Args:
        parsed: The parsed SQL expression
        default_limit: Default LIMIT to apply if none exists
        max_limit: Maximum allowed LIMIT value
        
    Returns:
        Modified expression with proper LIMIT
        
    Raises:
        SQLPolicyError: If LIMIT value is invalid
    """
    # Find existing LIMIT clause
    limit_clause = parsed.find(exp.Limit)
    
    if limit_clause is None:
        # No LIMIT - add default
        parsed = parsed.limit(default_limit)
    else:
        # LIMIT exists - validate and cap if necessary
        limit_expr = limit_clause.expression
        
        # Check if it's a literal number
        if isinstance(limit_expr, exp.Literal):
            if not limit_expr.is_int:
                raise SQLPolicyError(
                    "LIMIT must be an integer value. "
                    "Non-integer LIMIT values are not allowed."
                )
            
            limit_value = int(limit_expr.this)
            
            if limit_value < 0:
                raise SQLPolicyError("LIMIT cannot be negative.")
            
            if limit_value > max_limit:
                # Cap the limit
                limit_clause.set("expression", exp.Literal.number(max_limit))
        
        elif isinstance(limit_expr, exp.Parameter) or isinstance(limit_expr, exp.Placeholder):
            # Parameterized limits - reject for safety
            raise SQLPolicyError(
                "Parameterized LIMIT values are not allowed. "
                "Please specify a concrete integer LIMIT."
            )
        else:
            # Any other expression type for LIMIT
            raise SQLPolicyError(
                "LIMIT must be a simple integer value. "
                "Expressions and variables are not allowed."
            )
    
    return parsed


def is_safe_query(sql: str) -> tuple[bool, Optional[str]]:
    """
    Check if a query is safe without modifying it.
    
    Args:
        sql: The SQL query to check
        
    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        validate_sql(sql)
        return True, None
    except SQLPolicyError as e:
        return False, str(e)
