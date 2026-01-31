"""
Chat endpoint for Pharma Analyst Bot
"""
import time
import uuid
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.workflow import run_agent
from app.audit.repo import insert_audit_log
from app.services.llm import is_llm_available

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatMetadata(BaseModel):
    row_count: int
    runtime_ms: int


class ChartSpec(BaseModel):
    vega_lite_spec: Dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sql: Optional[str]
    assumptions: List[str]
    chart: ChartSpec
    follow_up_questions: List[str]
    metadata: ChatMetadata


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message and return SQL analysis results.
    
    Uses LangGraph workflow for:
    1. Preprocessing and normalization
    2. Scope/policy checking
    3. Schema grounding
    4. LLM-based SQL generation
    5. SQL validation
    6. Safe query execution
    7. LLM-based result summarization
    """
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    message = request.message.strip()
    
    # Check if LLM is available
    if not is_llm_available():
        runtime_ms = int((time.time() - start_time) * 1000)
        
        # Log this attempt
        insert_audit_log(
            session_id=session_id,
            question=message,
            sql_text=None,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text="OPENAI_API_KEY not set"
        )
        
        return ChatResponse(
            answer="LLM summarization is required but not available. Set OPENAI_API_KEY.",
            sql=None,
            assumptions=[],
            chart=ChartSpec(vega_lite_spec={}),
            follow_up_questions=[],
            metadata=ChatMetadata(row_count=0, runtime_ms=runtime_ms)
        )
    
    try:
        # Run the LangGraph workflow
        result = run_agent(session_id=session_id, user_question=message)
        
        # Extract results from state
        answer = result.get("answer", "I encountered an issue processing your request.")
        sql = result.get("sql_candidate")
        assumptions = result.get("assumptions", [])
        vega_spec = result.get("vega_lite_spec", {})
        follow_ups = result.get("follow_up_questions", [])
        row_count = result.get("row_count", 0)
        runtime_ms = result.get("runtime_ms", int((time.time() - start_time) * 1000))
        
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
            session_id=session_id,
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
            metadata=ChatMetadata(row_count=row_count, runtime_ms=runtime_ms)
        )
        
    except Exception as e:
        # Handle unexpected errors
        runtime_ms = int((time.time() - start_time) * 1000)
        
        insert_audit_log(
            session_id=session_id,
            question=message,
            sql_text=None,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text=f"Unexpected error: {str(e)}"
        )
        
        return ChatResponse(
            answer=f"I encountered an unexpected error: {str(e)}. Please try again.",
            sql=None,
            assumptions=[],
            chart=ChartSpec(vega_lite_spec={}),
            follow_up_questions=["Would you like to try a different question?"],
            metadata=ChatMetadata(row_count=0, runtime_ms=runtime_ms)
        )

