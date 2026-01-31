"""
LangGraph workflow for the Text-to-SQL agent.
"""
import time
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    """State for the Text-to-SQL agent workflow."""
    # Input
    session_id: str
    user_question: str
    
    # Preprocessing
    normalized_question: str
    
    # Scope/Policy check
    ambiguity_flag: bool
    follow_up_questions: List[str]
    refusal_flag: bool
    refusal_reason: Optional[str]
    
    # Schema grounding
    grounded_schema: Dict[str, List[str]]
    schema_info_string: str
    
    # SQL generation
    sql_candidate: Optional[str]
    validation_errors: List[str]
    
    # Retry
    attempts_remaining: int
    
    # Execution results
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_error: Optional[str]
    
    # Response
    assumptions: List[str]
    answer: str
    vega_lite_spec: Dict[str, Any]
    
    # Timing
    start_time: float
    runtime_ms: int


def preprocess_node(state: AgentState) -> AgentState:
    """
    Preprocess and normalize the user question.
    """
    question = state["user_question"].strip()
    
    # Basic normalization
    normalized = question
    
    # Remove excessive whitespace
    normalized = ' '.join(normalized.split())
    
    # Ensure question ends properly
    if not normalized.endswith(('?', '.', '!')):
        normalized = normalized + '?'
    
    return {
        **state,
        "normalized_question": normalized,
    }


def scope_policy_node(state: AgentState) -> AgentState:
    """
    Check if the question is in scope and allowed by policy.
    """
    from app.guardrails.validators import check_dump_request, check_sensitive_request
    
    question = state["normalized_question"]
    
    # Check for dump requests
    is_dump, dump_reason = check_dump_request(question)
    if is_dump:
        return {
            **state,
            "refusal_flag": True,
            "refusal_reason": dump_reason,
        }
    
    # Check for sensitive data requests
    is_sensitive, sensitive_reason = check_sensitive_request(question)
    if is_sensitive:
        return {
            **state,
            "refusal_flag": True,
            "refusal_reason": sensitive_reason,
        }
    
    # Check for ambiguous questions
    question_lower = question.lower()
    
    # Very short or vague questions
    word_count = len(question.split())
    if word_count < 3:
        return {
            **state,
            "ambiguity_flag": True,
            "follow_up_questions": [
                "Could you provide more details about what you'd like to know?",
                "What specific metrics or data are you interested in?",
                "Are you looking for data about products, territories, or sales?"
            ],
        }
    
    # Questions that are too vague
    vague_patterns = ["help", "something", "anything", "whatever", "stuff"]
    if any(p in question_lower for p in vague_patterns) and word_count < 6:
        return {
            **state,
            "ambiguity_flag": True,
            "follow_up_questions": [
                "What specific information would you like to see?",
                "Would you like to see top products by revenue?",
                "Are you interested in sales data by territory?"
            ],
        }
    
    return state


def clarifying_questions_node(state: AgentState) -> AgentState:
    """
    Generate clarifying questions for ambiguous input.
    Uses LLM if available, otherwise uses pre-defined questions.
    """
    from app.services.llm import is_llm_available, generate_clarifying_questions
    from app.services.answer import generate_clarification_answer
    
    # If we already have follow-up questions from scope check, use those
    if state.get("follow_up_questions"):
        answer = generate_clarification_answer(state["follow_up_questions"])
        return {
            **state,
            "answer": answer,
        }
    
    # Generate using LLM if available
    if is_llm_available():
        try:
            from app.agent.schema import get_schema_info_string
            schema_info = get_schema_info_string()
            questions = generate_clarifying_questions(
                state["normalized_question"],
                schema_info,
                "Question is ambiguous or needs more context"
            )
            answer = generate_clarification_answer(questions)
            return {
                **state,
                "follow_up_questions": questions,
                "answer": answer,
            }
        except Exception:
            pass
    
    # Fallback questions
    default_questions = [
        "What specific metrics are you interested in?",
        "Would you like to see data grouped by product, territory, or time period?",
        "What time range should I consider?"
    ]
    answer = generate_clarification_answer(default_questions)
    
    return {
        **state,
        "follow_up_questions": default_questions,
        "answer": answer,
    }


def schema_grounding_node(state: AgentState) -> AgentState:
    """
    Ground the schema based on the question.
    """
    from app.agent.schema import ground_schema_for_question, get_schema_info_string
    
    question = state["normalized_question"]
    grounded = ground_schema_for_question(question)
    schema_str = get_schema_info_string()
    
    return {
        **state,
        "grounded_schema": grounded,
        "schema_info_string": schema_str,
    }


def generate_sql_node(state: AgentState) -> AgentState:
    """
    Generate SQL using the LLM.
    """
    from app.services.llm import is_llm_available, generate_sql, fix_sql, LLMError
    
    if not is_llm_available():
        return {
            **state,
            "sql_candidate": None,
            "validation_errors": ["LLM not available - OPENAI_API_KEY not set"],
        }
    
    try:
        # Check if we're retrying with errors
        if state.get("validation_errors") and state.get("sql_candidate"):
            # Fix the previous SQL
            sql = fix_sql(
                original_sql=state["sql_candidate"] or "",
                error_message="; ".join(state["validation_errors"]),
                schema_info=state["schema_info_string"],
                user_question=state["normalized_question"]
            )
        else:
            # Generate fresh SQL
            sql = generate_sql(
                user_question=state["normalized_question"],
                schema_info=state["schema_info_string"]
            )
        
        # Basic assumptions based on what we're doing
        assumptions = []
        sql_lower = sql.lower() if sql else ""
        
        if "limit" not in sql_lower:
            assumptions.append("Results will be limited by system default (200 rows)")
        if "order by" in sql_lower and "desc" in sql_lower:
            assumptions.append("Results sorted by highest values first")
        if "sum(" in sql_lower or "count(" in sql_lower:
            assumptions.append("Data is aggregated across all matching records")
        
        return {
            **state,
            "sql_candidate": sql,
            "validation_errors": [],
            "assumptions": assumptions,
        }
        
    except LLMError as e:
        return {
            **state,
            "sql_candidate": None,
            "validation_errors": [str(e)],
        }


def validate_sql_node(state: AgentState) -> AgentState:
    """
    Validate the generated SQL against policies and schema.
    """
    from app.guardrails.validators import validate_sql_complete
    from app.guardrails.sql_policy import validate_sql, SQLPolicyError
    
    sql = state.get("sql_candidate")
    
    if not sql:
        return {
            **state,
            "validation_errors": state.get("validation_errors", []) or ["No SQL generated"],
        }
    
    # Run comprehensive validation
    is_valid, errors = validate_sql_complete(sql)
    
    if not is_valid:
        return {
            **state,
            "validation_errors": errors,
        }
    
    # Apply policy (adds LIMIT, etc.)
    try:
        validated_sql = validate_sql(sql)
        return {
            **state,
            "sql_candidate": validated_sql,
            "validation_errors": [],
        }
    except SQLPolicyError as e:
        return {
            **state,
            "validation_errors": [str(e)],
        }


def fix_retry_node(state: AgentState) -> AgentState:
    """
    Handle retry logic - decrement attempts and prepare for retry.
    """
    attempts = state.get("attempts_remaining", 3) - 1
    
    return {
        **state,
        "attempts_remaining": attempts,
    }


def execute_query_node(state: AgentState) -> AgentState:
    """
    Execute the validated SQL query.
    """
    from app.services.sql_exec import execute_query, SQLExecutionError
    
    sql = state.get("sql_candidate")
    
    if not sql:
        return {
            **state,
            "execution_error": "No SQL to execute",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }
    
    try:
        columns, rows, row_count = execute_query(sql)
        
        return {
            **state,
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "execution_error": None,
        }
        
    except SQLExecutionError as e:
        return {
            **state,
            "execution_error": str(e),
            "validation_errors": state.get("validation_errors", []) + [str(e)],
            "columns": [],
            "rows": [],
            "row_count": 0,
        }


def finalize_response_node(state: AgentState) -> AgentState:
    """
    Finalize the response with LLM-generated answer and chart.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from app.services.llm import is_llm_available, LLMError
    from app.services.answer import generate_answer, generate_error_answer
    from app.services.chart import generate_chart_spec
    from app.agent.schema import get_schema_summary
    
    # Calculate runtime
    runtime_ms = int((time.time() - state["start_time"]) * 1000)
    
    logger.info(f"finalize_response_node: rows={len(state.get('rows', []))}, columns={state.get('columns', [])}")
    
    # Check for refusal
    if state.get("refusal_flag"):
        return {
            **state,
            "answer": state.get("refusal_reason") or "Request not allowed.",
            "sql_candidate": None,
            "vega_lite_spec": {},
            "runtime_ms": runtime_ms,
        }
    
    # Check for ambiguity
    if state.get("ambiguity_flag"):
        return {
            **state,
            "sql_candidate": None,
            "vega_lite_spec": {},
            "runtime_ms": runtime_ms,
        }
    
    # Check if LLM is available
    if not is_llm_available():
        return {
            **state,
            "answer": "LLM summarization is required but not available. Set OPENAI_API_KEY.",
            "sql_candidate": None,
            "vega_lite_spec": {},
            "runtime_ms": runtime_ms,
            "row_count": 0,
        }
    
    # Check for execution error
    if state.get("execution_error"):
        answer = generate_error_answer(state["execution_error"] or "Unknown error", state["user_question"])
        return {
            **state,
            "answer": answer,
            "vega_lite_spec": {},
            "runtime_ms": runtime_ms,
            "follow_up_questions": [
                "Would you like to try a different question?",
                "Can you be more specific about what data you need?"
            ],
        }
    
    # Check for validation errors (after retries exhausted)
    if state.get("validation_errors"):
        error_msg = "; ".join(state["validation_errors"])
        return {
            **state,
            "answer": f"I couldn't generate a valid query: {error_msg}",
            "sql_candidate": None,
            "vega_lite_spec": {},
            "runtime_ms": runtime_ms,
            "follow_up_questions": [
                "Could you rephrase your question?",
                "What specific data would you like to see?"
            ],
        }
    
    # Generate answer using LLM
    try:
        answer = generate_answer(
            user_question=state["user_question"],
            sql_used=state.get("sql_candidate") or "",
            columns=state.get("columns", []),
            rows=state.get("rows", []),
            assumptions=state.get("assumptions", []),
            schema_summary=get_schema_summary(),
            row_count=state.get("row_count", 0)
        )
    except LLMError as e:
        return {
            **state,
            "answer": "LLM summarization is required but not available. Set OPENAI_API_KEY.",
            "sql_candidate": None,
            "vega_lite_spec": {},
            "runtime_ms": runtime_ms,
            "row_count": 0,
        }
    
    # Generate chart
    logger.info(f"Generating chart with columns={state.get('columns', [])}, row_count={len(state.get('rows', []))}")
    vega_spec = generate_chart_spec(
        columns=state.get("columns", []),
        rows=state.get("rows", []),
        sql=state.get("sql_candidate")
    )
    logger.info(f"Generated vega_spec: has_content={bool(vega_spec)}, keys={list(vega_spec.keys()) if vega_spec else []}")
    
    # Generate follow-up questions
    follow_ups = _generate_follow_ups(state.get("sql_candidate") or "", state.get("columns", []))
    
    return {
        **state,
        "answer": answer,
        "vega_lite_spec": vega_spec,
        "runtime_ms": runtime_ms,
        "follow_up_questions": follow_ups,
    }


def _generate_follow_ups(sql: str, columns: List[str]) -> List[str]:
    """Generate follow-up questions based on the query context."""
    follow_ups = []
    sql_lower = sql.lower() if sql else ""
    
    if "product" in sql_lower:
        follow_ups.append("How does this compare by territory?")
        follow_ups.append("What's the trend over the last few months?")
    elif "territory" in sql_lower:
        follow_ups.append("Which products perform best in each territory?")
        follow_ups.append("Show me the top HCPs by territory")
    elif "hcp" in sql_lower:
        follow_ups.append("What products do they prescribe most?")
        follow_ups.append("How does this compare to other HCPs?")
    else:
        follow_ups.append("What are the top products by revenue?")
        follow_ups.append("Show me revenue by territory")
    
    return follow_ups[:3]


# Router functions
def should_ask_clarification(state: AgentState) -> str:
    """Route based on ambiguity flag."""
    if state.get("ambiguity_flag"):
        return "clarify"
    if state.get("refusal_flag"):
        return "finalize"
    return "continue"


def should_retry(state: AgentState) -> str:
    """Route based on validation/execution errors and attempts."""
    has_errors = bool(state.get("validation_errors")) or bool(state.get("execution_error"))
    attempts_left = state.get("attempts_remaining", 0) > 0
    
    if has_errors and attempts_left:
        return "retry"
    return "finalize"


def build_workflow():
    """Build and compile the LangGraph workflow."""
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("scope_policy", scope_policy_node)
    workflow.add_node("clarify", clarifying_questions_node)
    workflow.add_node("schema_ground", schema_grounding_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("fix_retry", fix_retry_node)
    workflow.add_node("execute", execute_query_node)
    workflow.add_node("finalize", finalize_response_node)
    
    # Set entry point
    workflow.set_entry_point("preprocess")
    
    # Add edges
    workflow.add_edge("preprocess", "scope_policy")
    
    # Conditional edge after scope/policy check
    workflow.add_conditional_edges(
        "scope_policy",
        should_ask_clarification,
        {
            "clarify": "clarify",
            "finalize": "finalize",
            "continue": "schema_ground",
        }
    )
    
    workflow.add_edge("clarify", "finalize")
    workflow.add_edge("schema_ground", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    # Conditional edge after validation
    workflow.add_conditional_edges(
        "validate_sql",
        should_retry,
        {
            "retry": "fix_retry",
            "finalize": "execute",
        }
    )
    
    workflow.add_edge("fix_retry", "generate_sql")
    
    # Conditional edge after execution
    workflow.add_conditional_edges(
        "execute",
        should_retry,
        {
            "retry": "fix_retry",
            "finalize": "finalize",
        }
    )
    
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


# Singleton compiled workflow
_compiled_workflow = None


def get_workflow():
    """Get the compiled workflow (singleton)."""
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_workflow()
    return _compiled_workflow


def run_agent(session_id: str, user_question: str) -> Dict[str, Any]:
    """
    Run the agent workflow.
    
    Args:
        session_id: Session identifier
        user_question: User's natural language question
        
    Returns:
        Final agent state with results
    """
    workflow = get_workflow()
    
    initial_state: AgentState = {
        "session_id": session_id,
        "user_question": user_question,
        "normalized_question": "",
        "ambiguity_flag": False,
        "follow_up_questions": [],
        "refusal_flag": False,
        "refusal_reason": None,
        "grounded_schema": {},
        "schema_info_string": "",
        "sql_candidate": None,
        "validation_errors": [],
        "attempts_remaining": 3,
        "columns": [],
        "rows": [],
        "row_count": 0,
        "execution_error": None,
        "assumptions": [],
        "answer": "",
        "vega_lite_spec": {},
        "start_time": time.time(),
        "runtime_ms": 0,
    }
    
    final_state = workflow.invoke(initial_state)
    
    return final_state
