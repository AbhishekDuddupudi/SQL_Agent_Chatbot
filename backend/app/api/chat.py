"""
Chat endpoint for Pharma Analyst Bot
"""
import time
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.agent.workflow import run_agent
from app.audit.repo import insert_audit_log
from app.services.llm import is_llm_available
from app.api.auth import require_auth
from app.services.chat_history import (
    create_session as create_chat_session,
    get_session,
    add_message,
    get_recent_messages,
    auto_title_session,
    should_auto_title,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: Optional[int] = None  # Now an integer (DB session ID)
    message: str


class ChatMetadata(BaseModel):
    row_count: int
    runtime_ms: int
    session_id: int  # Return session ID so frontend can track it


class ChartSpec(BaseModel):
    vega_lite_spec: Dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sql: Optional[str]
    assumptions: List[str]
    chart: ChartSpec
    follow_up_questions: List[str]
    metadata: ChatMetadata


def build_conversation_context(session_id: int) -> str:
    """
    Build conversation context from recent messages (memory window).
    Returns formatted string for LLM context.
    """
    recent = get_recent_messages(session_id, limit=5)
    
    if not recent:
        return ""
    
    context_lines = ["Previous conversation:"]
    for msg in recent:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        # Truncate long messages for context
        content = msg["content"][:500] + "..." if len(msg["content"]) > 500 else msg["content"]
        context_lines.append(f"{role_label}: {content}")
    
    return "\n".join(context_lines)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request, user: dict = Depends(require_auth)):
    """
    Process a chat message and return SQL analysis results.
    Requires authentication. Stores messages in chat history.
    
    If session_id is not provided, creates a new session automatically.
    """
    start_time = time.time()
    user_id = user["id"]
    message = request.message.strip()
    
    # Get or create session
    if request.session_id:
        # Verify session belongs to user
        session = get_session(request.session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = request.session_id
    else:
        # Create new session automatically
        session = create_chat_session(user_id)
        session_id = session["id"]
    
    # Check if we should auto-title (first message)
    needs_title = should_auto_title(session_id)
    
    # Store user message
    add_message(session_id, role="user", content=message)
    
    # Auto-title if this is the first message
    if needs_title:
        auto_title_session(session_id, message)
    
    # Build conversation context from recent messages
    conversation_context = build_conversation_context(session_id)
    
    # Check if LLM is available
    if not is_llm_available():
        runtime_ms = int((time.time() - start_time) * 1000)
        
        error_answer = "LLM summarization is required but not available. Set OPENAI_API_KEY."
        add_message(session_id, role="assistant", content=error_answer)
        
        insert_audit_log(
            session_id=str(session_id),
            question=message,
            sql_text=None,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text="OPENAI_API_KEY not set"
        )
        
        return ChatResponse(
            answer=error_answer,
            sql=None,
            assumptions=[],
            chart=ChartSpec(vega_lite_spec={}),
            follow_up_questions=[],
            metadata=ChatMetadata(row_count=0, runtime_ms=runtime_ms, session_id=session_id)
        )
    
    try:
        # Run the LangGraph workflow with conversation context
        result = run_agent(
            session_id=str(session_id),
            user_question=message,
            conversation_context=conversation_context
        )
        
        # Extract results from state
        answer = result.get("answer", "I encountered an issue processing your request.")
        sql = result.get("sql_candidate")
        assumptions = result.get("assumptions", [])
        vega_spec = result.get("vega_lite_spec", {})
        follow_ups = result.get("follow_up_questions", [])
        row_count = result.get("row_count", 0)
        runtime_ms = result.get("runtime_ms", int((time.time() - start_time) * 1000))
        
        # Store assistant message
        add_message(session_id, role="assistant", content=answer, sql_query=sql)
        
        logger.info(f"Chat API: vega_spec has content={bool(vega_spec)}, keys={list(vega_spec.keys()) if vega_spec else []}")
        
        # Determine status for audit
        error_text = None
        if result.get("refusal_flag"):
            error_text = f"Refused: {result.get('refusal_reason', 'Policy violation')}"
        elif result.get("ambiguity_flag"):
            error_text = "Needs clarification"
        elif result.get("validation_errors"):
            error_text = f"Validation errors: {'; '.join(result['validation_errors'])}"
        elif result.get("execution_error"):
            error_text = f"Execution error: {result['execution_error']}"
        
        # Insert audit log
        insert_audit_log(
            session_id=str(session_id),
            question=message,
            sql_text=sql,
            runtime_ms=runtime_ms,
            row_count=row_count,
            error_text=error_text
        )
        
        return ChatResponse(
            answer=answer,
            sql=sql,
            assumptions=assumptions,
            chart=ChartSpec(vega_lite_spec=vega_spec),
            follow_up_questions=follow_ups,
            metadata=ChatMetadata(row_count=row_count, runtime_ms=runtime_ms, session_id=session_id)
        )
        
    except Exception as e:
        # Handle unexpected errors
        runtime_ms = int((time.time() - start_time) * 1000)
        
        error_answer = f"I encountered an unexpected error: {str(e)}. Please try again."
        add_message(session_id, role="assistant", content=error_answer)
        
        insert_audit_log(
            session_id=str(session_id),
            question=message,
            sql_text=None,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text=f"Unexpected error: {str(e)}"
        )
        
        return ChatResponse(
            answer=error_answer,
            sql=None,
            assumptions=[],
            chart=ChartSpec(vega_lite_spec={}),
            follow_up_questions=["Would you like to try a different question?"],
            metadata=ChatMetadata(row_count=0, runtime_ms=runtime_ms, session_id=session_id)
        )

