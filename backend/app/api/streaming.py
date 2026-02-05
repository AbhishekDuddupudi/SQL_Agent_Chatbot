"""
Server-Sent Events (SSE) streaming endpoint for chat.
"""
import json
import time
import uuid
import logging
import asyncio
from typing import Optional, AsyncGenerator, Dict, Any, List

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


class StreamChatRequest(BaseModel):
    session_id: Optional[int] = None  # Database session ID (integer)
    message: str


# Event types for SSE
EVENT_STATUS = "status"
EVENT_TOKEN = "token"
EVENT_COMPLETE = "complete"
EVENT_ERROR = "error"


def format_sse_event(event_type: str, data: Dict[str, Any], request_id: str) -> str:
    """Format data as an SSE event."""
    payload = {
        "request_id": request_id,
        "timestamp": time.time(),
        **data
    }
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


def build_conversation_context(session_id: int) -> str:
    """Build conversation context from recent messages."""
    from app.services.chat_history import get_recent_messages
    
    recent_messages = get_recent_messages(session_id, limit=5)
    if not recent_messages:
        return ""
    
    context_lines = []
    for msg in recent_messages:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        context_lines.append(f"{role_label}: {msg['content']}")
    
    return "\n\n".join(context_lines)


class StreamingWorkflowRunner:
    """
    Runs the LangGraph workflow with streaming callbacks.
    Emits status events as each step progresses.
    """
    
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.events: asyncio.Queue = asyncio.Queue()
        self.start_time = time.time()
        
    def emit_status(self, step: str, message: str):
        """Emit a status event."""
        event = format_sse_event(EVENT_STATUS, {
            "step": step,
            "message": message
        }, self.request_id)
        self.events.put_nowait(event)
        
    def emit_token(self, token: str):
        """Emit a token during answer streaming."""
        event = format_sse_event(EVENT_TOKEN, {
            "token": token
        }, self.request_id)
        self.events.put_nowait(event)
        
    def emit_complete(self, result: Dict[str, Any]):
        """Emit the complete event with full response."""
        runtime_ms = int((time.time() - self.start_time) * 1000)
        event = format_sse_event(EVENT_COMPLETE, {
            "answer": result.get("answer", ""),
            "sql": result.get("sql_candidate"),
            "assumptions": result.get("assumptions", []),
            "chart": {"vega_lite_spec": result.get("vega_lite_spec", {})},
            "follow_up_questions": result.get("follow_up_questions", []),
            "metadata": {
                "row_count": result.get("row_count", 0),
                "runtime_ms": runtime_ms
            }
        }, self.request_id)
        self.events.put_nowait(event)
        
    def emit_error(self, error_message: str):
        """Emit an error event."""
        event = format_sse_event(EVENT_ERROR, {
            "error": error_message
        }, self.request_id)
        self.events.put_nowait(event)
        
    async def run_workflow_streaming(
        self, 
        session_id: str, 
        user_question: str,
        conversation_context: str = ""
    ) -> Dict[str, Any]:
        """
        Run the workflow with status callbacks for streaming.
        """
        from app.services.llm import is_llm_available, generate_sql, fix_sql
        from app.agent.schema import get_allowed_schema, get_schema_info_string
        from app.guardrails.validators import (
            check_dump_request, 
            check_sensitive_request,
            validate_sql_complete
        )
        from app.guardrails.sql_policy import validate_sql
        from app.services.sql_exec import execute_query, SQLExecutionError
        from app.services.chart import generate_chart_spec
        
        # Step 1: Analyzing question
        self.emit_status("analyzing_question", "Analyzing your question...")
        await asyncio.sleep(0.05)  # Small delay to ensure event is sent
        
        # Check LLM availability
        if not is_llm_available():
            return {
                "answer": "LLM summarization is required but not available. Set OPENAI_API_KEY.",
                "sql_candidate": None,
                "assumptions": [],
                "vega_lite_spec": {},
                "follow_up_questions": [],
                "row_count": 0
            }
        
        # Normalize question
        normalized = ' '.join(user_question.strip().split())
        if not normalized.endswith(('?', '.', '!')):
            normalized = normalized + '?'
            
        # Check for policy violations
        is_dump, dump_reason = check_dump_request(normalized)
        if is_dump:
            return {
                "answer": f"I cannot help with that request: {dump_reason}",
                "sql_candidate": None,
                "assumptions": [],
                "vega_lite_spec": {},
                "follow_up_questions": ["Try asking about specific products or territories."],
                "row_count": 0,
                "refusal_flag": True
            }
            
        is_sensitive, sensitive_reason = check_sensitive_request(normalized)
        if is_sensitive:
            return {
                "answer": f"I cannot help with that request: {sensitive_reason}",
                "sql_candidate": None,
                "assumptions": [],
                "vega_lite_spec": {},
                "follow_up_questions": ["Try asking about sales, products, or territories."],
                "row_count": 0,
                "refusal_flag": True
            }
        
        # Step 2: Generating SQL
        self.emit_status("generating_sql", "Generating SQL query...")
        await asyncio.sleep(0.05)
        
        # Get schema and generate SQL
        schema = get_allowed_schema()
        schema_info = get_schema_info_string()
        
        sql_candidate: Optional[str] = None
        validation_errors: List[str] = []
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                if attempt == 0:
                    sql_candidate = generate_sql(normalized, schema_info)
                else:
                    self.emit_status("fixing_sql", f"Fixing SQL (attempt {attempt + 1}/{max_attempts})...")
                    await asyncio.sleep(0.05)
                    error_msg = "; ".join(validation_errors)
                    sql_candidate = fix_sql(sql_candidate or "", error_msg, schema_info, normalized)
                
                if not sql_candidate:
                    validation_errors = ["Failed to generate SQL"]
                    continue
                
                # Validate SQL
                try:
                    validated_sql = validate_sql(sql_candidate)
                    sql_candidate = validated_sql
                    
                    is_valid, errors = validate_sql_complete(sql_candidate)
                    
                    if is_valid:
                        validation_errors = []
                        break
                    else:
                        validation_errors = errors
                        
                except Exception as e:
                    validation_errors = [str(e)]
                    
            except Exception as e:
                validation_errors = [f"SQL generation failed: {str(e)}"]
        
        # If still invalid after retries
        if validation_errors:
            return {
                "answer": f"I couldn't generate a valid query: {'; '.join(validation_errors)}",
                "sql_candidate": sql_candidate,
                "assumptions": [],
                "vega_lite_spec": {},
                "follow_up_questions": ["Could you rephrase your question?"],
                "row_count": 0
            }
        
        # Step 3: Executing SQL
        self.emit_status("executing_sql", "Executing query...")
        await asyncio.sleep(0.05)
        
        try:
            columns, rows, row_count = execute_query(sql_candidate or "")
        except SQLExecutionError as e:
            return {
                "answer": f"Query execution failed: {str(e)}",
                "sql_candidate": sql_candidate,
                "assumptions": [],
                "vega_lite_spec": {},
                "follow_up_questions": ["Try asking in a different way."],
                "row_count": 0
            }
        except Exception as e:
            return {
                "answer": f"Query execution failed: {str(e)}",
                "sql_candidate": sql_candidate,
                "assumptions": [],
                "vega_lite_spec": {},
                "follow_up_questions": ["Try asking in a different way."],
                "row_count": 0
            }
        
        # Step 4: Summarizing with streaming
        self.emit_status("summarizing_answer", "Generating answer...")
        await asyncio.sleep(0.05)
        
        # Generate answer with streaming
        answer = await self._generate_answer_streaming(
            user_question=normalized,
            sql_used=sql_candidate or "",
            columns=columns,
            rows=rows
        )
        
        # Generate chart
        vega_spec = generate_chart_spec(
            columns=columns,
            rows=rows,
            sql=sql_candidate or ""
        )
        
        # Generate follow-up questions
        follow_ups = self._generate_follow_ups(sql_candidate or "", columns)
        
        # Build assumptions
        assumptions = ["Results sorted by highest values first"]
        if row_count > 0:
            assumptions.append("Data is aggregated across all matching records")
        
        return {
            "answer": answer,
            "sql_candidate": sql_candidate,
            "assumptions": assumptions,
            "vega_lite_spec": vega_spec,
            "follow_up_questions": follow_ups,
            "row_count": row_count,
            "columns": columns,
            "rows": rows
        }
    
    async def _generate_answer_streaming(
        self,
        user_question: str,
        sql_used: str,
        columns: List[str],
        rows: List[Dict[str, Any]]
    ) -> str:
        """Generate answer with token streaming."""
        from app.services.llm import _get_openai_client
        from app.agent.prompts import get_summarization_prompt
        from openai.types.chat import ChatCompletionMessageParam
        
        # Prepare messages
        display_rows = rows[:50]
        rows_text = json.dumps(display_rows, indent=2, default=str)
        
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": get_summarization_prompt()},
            {"role": "user", "content": f"""
User Question: {user_question}

SQL Executed:
{sql_used}

Result Columns: {', '.join(columns)}

Result Data (up to 50 rows):
{rows_text}

Please provide a concise, business-friendly summary of these results.
"""}
        ]
        
        try:
            client = _get_openai_client()
            
            # Stream the response
            full_answer = ""
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.2,
                max_tokens=500,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_answer += token
                    self.emit_token(token)
                    await asyncio.sleep(0.01)  # Small delay for smooth streaming
            
            return full_answer.strip()
            
        except Exception as e:
            logger.error(f"Streaming answer generation failed: {e}")
            # Fallback to non-streaming
            from app.services.llm import summarize_results
            from app.agent.schema import get_schema_summary
            return summarize_results(
                user_question=user_question,
                sql_used=sql_used,
                columns=columns,
                rows=rows,
                assumptions=[],
                schema_summary=get_schema_summary()
            )
    
    def _generate_follow_ups(self, sql: str, columns: List[str]) -> List[str]:
        """Generate follow-up questions based on context."""
        follow_ups = []
        sql_lower = sql.lower() if sql else ""
        
        if "product" in sql_lower:
            follow_ups.extend([
                "How does this compare by territory?",
                "What's the trend over the last few months?"
            ])
        elif "territory" in sql_lower:
            follow_ups.extend([
                "Which products perform best in each territory?",
                "Show me the top HCPs by territory"
            ])
        elif "hcp" in sql_lower:
            follow_ups.extend([
                "What products do they prescribe most?",
                "How does this compare to other HCPs?"
            ])
        else:
            follow_ups.extend([
                "What are the top products by revenue?",
                "Show me revenue by territory"
            ])
        
        return follow_ups[:3]


async def stream_chat_response(
    session_id: int,
    user_id: int,
    message: str,
    request_id: str
) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE events for the chat response.
    """
    from app.audit.repo import insert_audit_log
    from app.services.chat_history import (
        add_message, 
        should_auto_title, 
        auto_title_session
    )
    
    runner = StreamingWorkflowRunner(request_id)
    start_time = time.time()
    
    # Store user message
    add_message(session_id, "user", message)
    
    # Auto-title on first user message
    if should_auto_title(session_id):
        auto_title_session(session_id, message)
    
    # Build conversation context for memory
    conversation_context = build_conversation_context(session_id)
    
    try:
        # Run workflow in a separate task so we can yield events
        workflow_task = asyncio.create_task(
            runner.run_workflow_streaming(str(session_id), message, conversation_context)
        )
        
        # Yield events as they come in
        while not workflow_task.done():
            try:
                # Get event with timeout
                event = await asyncio.wait_for(
                    runner.events.get(), 
                    timeout=0.1
                )
                yield event
            except asyncio.TimeoutError:
                continue
        
        # Drain any remaining events
        while not runner.events.empty():
            event = runner.events.get_nowait()
            yield event
        
        # Get final result
        result = await workflow_task
        
        # Store assistant response
        add_message(
            session_id, 
            "assistant", 
            result.get("answer", ""),
            sql_query=result.get("sql_candidate")
        )
        
        # Emit complete event
        runner.emit_complete(result)
        yield runner.events.get_nowait()
        
        # Log to audit
        runtime_ms = int((time.time() - start_time) * 1000)
        insert_audit_log(
            session_id=str(session_id),
            question=message,
            sql_text=result.get("sql_candidate"),
            runtime_ms=runtime_ms,
            row_count=result.get("row_count", 0),
            error_text=None if not result.get("refusal_flag") else "Refused"
        )
        
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        
        # Emit error event
        runner.emit_error(str(e))
        yield runner.events.get_nowait()
        
        # Log error to audit
        runtime_ms = int((time.time() - start_time) * 1000)
        insert_audit_log(
            session_id=str(session_id),
            question=message,
            sql_text=None,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text=f"Streaming error: {str(e)}"
        )


@router.post("/chat/stream")
async def chat_stream(request: StreamChatRequest, http_request: Request, user: dict = Depends(require_auth)):
    """
    Stream chat response using Server-Sent Events.
    Requires authentication.
    
    Events:
    - status: Workflow progress updates (analyzing_question, generating_sql, executing_sql, summarizing_answer)
    - token: Individual tokens during answer generation
    - complete: Full response with all data
    - error: Error information
    
    All events include request_id for debugging.
    """
    from app.services.chat_history import create_session, get_session
    
    request_id = str(uuid.uuid4())
    message = request.message.strip()
    user_id = user['id']
    
    if not message:
        async def error_stream():
            yield format_sse_event(EVENT_ERROR, {
                "error": "Message cannot be empty"
            }, request_id)
        
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Get or create session
    session_id = request.session_id
    if session_id:
        # Verify session belongs to user
        session = get_session(session_id)
        if not session or session["user_id"] != user_id:
            async def error_stream():
                yield format_sse_event(EVENT_ERROR, {
                    "error": "Session not found or access denied"
                }, request_id)
            
            return StreamingResponse(
                error_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
    else:
        # Create new session
        new_session = create_session(user_id)
        session_id = new_session["id"]
    
    async def stream_with_session_id():
        """Wrap stream to include session_id in first event."""
        # Send session_id as first event so frontend knows which session to use
        yield format_sse_event("session", {"session_id": session_id}, request_id)
        async for event in stream_chat_response(session_id, user_id, message, request_id):
            yield event
    
    return StreamingResponse(
        stream_with_session_id(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
