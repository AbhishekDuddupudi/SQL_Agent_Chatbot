"""
Answer generation service - LLM-based summarization only.
"""
from typing import List, Dict, Any

from app.services.llm import summarize_results, is_llm_available, LLMError


def generate_answer(
    user_question: str,
    sql_used: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    assumptions: List[str],
    schema_summary: str,
    row_count: int
) -> str:
    """
    Generate a business-friendly answer for query results.
    
    This function REQUIRES LLM summarization - no heuristic fallback.
    
    Args:
        user_question: Original user question
        sql_used: The SQL query that was executed
        columns: Column names from result
        rows: Result rows
        assumptions: Assumptions made during query generation
        schema_summary: Brief schema context
        row_count: Total row count
        
    Returns:
        Human-readable answer string
        
    Raises:
        LLMError: If LLM is not available or fails
    """
    if not is_llm_available():
        raise LLMError("LLM summarization is required but OPENAI_API_KEY is not set")
    
    # Handle empty results
    if row_count == 0:
        return summarize_results(
            user_question=user_question,
            sql_used=sql_used,
            columns=columns,
            rows=[],
            assumptions=assumptions,
            schema_summary=schema_summary
        )
    
    # Generate LLM summary
    answer = summarize_results(
        user_question=user_question,
        sql_used=sql_used,
        columns=columns,
        rows=rows,  # Already limited by caller
        assumptions=assumptions,
        schema_summary=schema_summary
    )
    
    return answer


def generate_refusal_answer(reason: str) -> str:
    """
    Generate an answer explaining why a query was refused.
    
    Args:
        reason: The reason for refusal
        
    Returns:
        User-friendly refusal message
    """
    return f"I'm unable to process this request. {reason}"


def generate_error_answer(error: str, user_question: str) -> str:
    """
    Generate an answer explaining a query error.
    
    Args:
        error: The error that occurred
        user_question: Original question for context
        
    Returns:
        User-friendly error message
    """
    return f"I encountered an issue while processing your query: {error}. Please try rephrasing your question."


def generate_clarification_answer(follow_up_questions: List[str]) -> str:
    """
    Generate an answer asking for clarification.
    
    Args:
        follow_up_questions: Questions to ask the user
        
    Returns:
        User-friendly clarification request
    """
    if not follow_up_questions:
        return "I need more details to answer your question. Could you please be more specific?"
    
    return "I'd like to help, but I need a bit more information to give you an accurate answer. Please see the follow-up questions below."
