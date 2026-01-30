"""
LLM client wrapper with retries and timeouts.
"""
import os
import json
from typing import Optional, List, Dict, Any

# OpenAI client will be lazy-loaded
_openai_client = None


class LLMError(Exception):
    """Exception raised when LLM operations fail."""
    pass


def _get_openai_client():
    """Get or create OpenAI client (lazy initialization)."""
    global _openai_client
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("OPENAI_API_KEY environment variable is not set")
    
    if _openai_client is None:
        try:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=api_key)
        except ImportError:
            raise LLMError("openai package is not installed")
    
    return _openai_client


def is_llm_available() -> bool:
    """Check if LLM is available (API key is set)."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def chat_completion(
    messages: List[Dict[str, Any]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
    max_tokens: int = 2000,
    timeout: float = 30.0,
    retries: int = 2
) -> str:
    """
    Call OpenAI chat completion with retries.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use
        temperature: Sampling temperature
        max_tokens: Maximum response tokens
        timeout: Request timeout in seconds
        retries: Number of retry attempts
        
    Returns:
        The assistant's response text
        
    Raises:
        LLMError: If the call fails after retries
    """
    client = _get_openai_client()
    
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            if attempt < retries:
                continue
    
    raise LLMError(f"LLM call failed after {retries + 1} attempts: {last_error}")


def generate_sql(
    user_question: str,
    schema_info: str,
    dialect: str = "postgres"
) -> str:
    """
    Generate SQL query from natural language question.
    
    Args:
        user_question: The user's natural language question
        schema_info: String describing available tables and columns
        dialect: SQL dialect to use
        
    Returns:
        Generated SQL query string
    """
    from app.agent.prompts import get_sql_generation_prompt
    
    messages = [
        {"role": "system", "content": get_sql_generation_prompt(schema_info, dialect)},
        {"role": "user", "content": user_question}
    ]
    
    response = chat_completion(messages, temperature=0.0)
    
    # Extract SQL from response (handle markdown code blocks)
    sql = _extract_sql(response)
    return sql


def fix_sql(
    original_sql: str,
    error_message: str,
    schema_info: str,
    user_question: str
) -> str:
    """
    Fix SQL query based on error message.
    
    Args:
        original_sql: The SQL that failed
        error_message: The error that occurred
        schema_info: Available schema information
        user_question: Original user question for context
        
    Returns:
        Fixed SQL query string
    """
    from app.agent.prompts import get_sql_fix_prompt
    
    messages = [
        {"role": "system", "content": get_sql_fix_prompt(schema_info)},
        {"role": "user", "content": f"""
User Question: {user_question}

Original SQL:
{original_sql}

Error:
{error_message}

Please fix the SQL query.
"""}
    ]
    
    response = chat_completion(messages, temperature=0.0)
    sql = _extract_sql(response)
    return sql


def generate_clarifying_questions(
    user_question: str,
    schema_info: str,
    ambiguity_reason: str
) -> List[str]:
    """
    Generate clarifying questions for ambiguous user input.
    
    Args:
        user_question: The ambiguous question
        schema_info: Available schema information
        ambiguity_reason: Why the question is ambiguous
        
    Returns:
        List of clarifying questions
    """
    from app.agent.prompts import get_clarifying_questions_prompt
    
    messages = [
        {"role": "system", "content": get_clarifying_questions_prompt(schema_info)},
        {"role": "user", "content": f"""
User Question: {user_question}

Ambiguity: {ambiguity_reason}

Generate 2-3 clarifying questions.
"""}
    ]
    
    response = chat_completion(messages, temperature=0.3)
    
    # Parse questions from response
    questions = []
    for line in response.strip().split('\n'):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
            # Remove numbering/bullets
            cleaned = line.lstrip('0123456789.-•) ').strip()
            if cleaned and '?' in cleaned:
                questions.append(cleaned)
    
    if not questions:
        # Fallback: split by question marks
        parts = response.split('?')
        questions = [p.strip() + '?' for p in parts if p.strip()][:3]
    
    return questions[:3]


def summarize_results(
    user_question: str,
    sql_used: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    assumptions: List[str],
    schema_summary: str
) -> str:
    """
    Generate a business-friendly answer summarizing query results.
    
    Args:
        user_question: Original user question
        sql_used: The SQL query that was executed
        columns: Column names from result
        rows: Result rows (limited to first 50)
        assumptions: Assumptions made during query generation
        schema_summary: Brief schema context
        
    Returns:
        Human-readable summary of the results
    """
    from app.agent.prompts import get_summarization_prompt
    
    # Format rows for display (limit to 50)
    display_rows = rows[:50]
    rows_text = json.dumps(display_rows, indent=2, default=str)
    
    messages = [
        {"role": "system", "content": get_summarization_prompt()},
        {"role": "user", "content": f"""
User Question: {user_question}

SQL Executed:
{sql_used}

Result Columns: {', '.join(columns)}

Result Data (up to 50 rows):
{rows_text}

Assumptions Made: {', '.join(assumptions) if assumptions else 'None'}

Schema Context: {schema_summary}

Please provide a concise, business-friendly summary of these results. 
Only reference numbers that appear in the data. Do not hallucinate.
"""}
    ]
    
    response = chat_completion(messages, temperature=0.2, max_tokens=500)
    return response.strip()


def _extract_sql(response: str) -> str:
    """Extract SQL from LLM response, handling markdown code blocks."""
    response = response.strip()
    
    # Check for markdown code blocks
    if '```sql' in response.lower():
        start = response.lower().find('```sql') + 6
        end = response.find('```', start)
        if end > start:
            return response[start:end].strip()
    
    if '```' in response:
        start = response.find('```') + 3
        # Skip language identifier if present
        newline = response.find('\n', start)
        if newline > start and newline - start < 20:
            start = newline + 1
        end = response.find('```', start)
        if end > start:
            return response[start:end].strip()
    
    # No code blocks, assume entire response is SQL
    # Remove any leading "SQL:" or similar prefixes
    if response.upper().startswith('SQL:'):
        response = response[4:].strip()
    
    return response
