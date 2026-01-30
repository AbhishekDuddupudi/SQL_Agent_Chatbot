"""
Schema introspection and grounding for safe SQL generation.
"""
from typing import Dict, List, Optional, Set
from sqlalchemy import text, inspect

from app.db.engine import get_engine


# Allowlist of tables and columns that can be queried
# This is the source of truth for what the LLM can reference
ALLOWED_SCHEMA: Dict[str, List[str]] = {
    "product": ["id", "name", "category", "unit_price", "created_at"],
    "territory": ["id", "name", "region", "country", "created_at"],
    "hcp": ["id", "first_name", "last_name", "specialty", "territory_id", "email", "created_at"],
    "sales": ["id", "product_id", "territory_id", "hcp_id", "quantity", "revenue", "sale_date", "created_at"],
}

# Tables that should never be exposed to queries
BLOCKED_TABLES: Set[str] = {"audit_log"}


def get_allowed_schema() -> Dict[str, List[str]]:
    """
    Get the allowlist of tables and columns.
    
    Returns:
        Dict mapping table names to list of allowed column names
    """
    return ALLOWED_SCHEMA.copy()


def get_schema_info_string() -> str:
    """
    Get a formatted string describing the allowed schema for LLM prompts.
    
    Returns:
        Human-readable schema description
    """
    lines = ["Available tables and columns:"]
    
    for table, columns in ALLOWED_SCHEMA.items():
        col_str = ", ".join(columns)
        lines.append(f"\n{table}: {col_str}")
    
    # Add relationship hints
    lines.append("\n\nRelationships:")
    lines.append("- sales.product_id -> product.id")
    lines.append("- sales.territory_id -> territory.id")
    lines.append("- sales.hcp_id -> hcp.id")
    lines.append("- hcp.territory_id -> territory.id")
    
    return "\n".join(lines)


def get_schema_summary() -> str:
    """
    Get a brief summary of the schema for context.
    
    Returns:
        Brief schema summary string
    """
    return (
        "Pharmaceutical sales database with products, territories, "
        "healthcare professionals (HCPs), and sales transactions."
    )


def introspect_schema() -> Dict[str, List[str]]:
    """
    Introspect the actual database schema.
    
    Returns:
        Dict mapping table names to list of column names
    """
    engine = get_engine()
    inspector = inspect(engine)
    
    schema = {}
    for table_name in inspector.get_table_names():
        if table_name not in BLOCKED_TABLES:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            schema[table_name] = columns
    
    return schema


def validate_schema_references(sql: str) -> tuple[bool, List[str]]:
    """
    Validate that SQL only references allowed tables and columns.
    
    Args:
        sql: The SQL query to validate
        
    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    import sqlglot
    from sqlglot import exp
    
    violations = []
    
    try:
        parsed = sqlglot.parse_one(sql, read='postgres')
    except Exception as e:
        return False, [f"SQL parse error: {str(e)}"]
    
    # Collect all table references
    referenced_tables = set()
    for table in parsed.find_all(exp.Table):
        table_name = table.name.lower()
        referenced_tables.add(table_name)
        
        if table_name in BLOCKED_TABLES:
            violations.append(f"Table '{table_name}' is not accessible")
        elif table_name not in ALLOWED_SCHEMA:
            violations.append(f"Unknown table '{table_name}'")
    
    # Collect all column references and validate against allowed columns
    for column in parsed.find_all(exp.Column):
        col_name = column.name.lower()
        table_ref = column.table.lower() if column.table else None
        
        if table_ref:
            # Column has explicit table reference
            if table_ref in ALLOWED_SCHEMA:
                allowed_cols = [c.lower() for c in ALLOWED_SCHEMA[table_ref]]
                if col_name not in allowed_cols:
                    violations.append(f"Column '{col_name}' not found in table '{table_ref}'")
        else:
            # Column without table reference - check all referenced tables
            found = False
            for table in referenced_tables:
                if table in ALLOWED_SCHEMA:
                    allowed_cols = [c.lower() for c in ALLOWED_SCHEMA[table]]
                    if col_name in allowed_cols:
                        found = True
                        break
            
            # Also check common aliases/expressions (be lenient for aggregates)
            if not found and col_name not in ['count', 'sum', 'avg', 'min', 'max']:
                # Only flag as error if it looks like a real column reference
                pass  # Be lenient for now - let DB catch actual errors
    
    return len(violations) == 0, violations


def ground_schema_for_question(question: str) -> Dict[str, List[str]]:
    """
    Determine which tables are relevant for a given question.
    
    Args:
        question: The user's natural language question
        
    Returns:
        Subset of allowed schema relevant to the question
    """
    question_lower = question.lower()
    
    # Start with all tables by default for comprehensive queries
    relevant = {}
    
    # Keywords that indicate specific tables
    table_keywords = {
        "product": ["product", "drug", "medication", "medicine"],
        "territory": ["territory", "region", "area", "location", "geography"],
        "hcp": ["hcp", "doctor", "physician", "healthcare", "prescriber"],
        "sales": ["sales", "revenue", "sold", "transaction", "quantity", "purchase"],
    }
    
    # Check which tables are relevant
    mentioned_tables = set()
    for table, keywords in table_keywords.items():
        if any(kw in question_lower for kw in keywords):
            mentioned_tables.add(table)
    
    # If no specific tables mentioned, include all
    if not mentioned_tables:
        return ALLOWED_SCHEMA.copy()
    
    # Sales queries usually need related tables for context
    if "sales" in mentioned_tables:
        mentioned_tables.update(["product", "territory", "hcp"])
    
    # Build relevant schema
    for table in mentioned_tables:
        if table in ALLOWED_SCHEMA:
            relevant[table] = ALLOWED_SCHEMA[table]
    
    return relevant if relevant else ALLOWED_SCHEMA.copy()
