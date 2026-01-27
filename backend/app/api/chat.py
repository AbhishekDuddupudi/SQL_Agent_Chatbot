"""
Chat endpoint for Pharma Analyst Bot
"""
import time
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db.engine import get_engine
from app.agent.stub_sql import route_intent
from app.guardrails.sql_policy import validate_sql, SQLPolicyError
from app.audit.repo import insert_audit_log

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


def generate_vega_lite_spec(data: List[Dict], sql: Optional[str]) -> Dict[str, Any]:
    """Generate a simple Vega-Lite spec based on the data."""
    if not data or not sql:
        return {}
    
    # Check if this looks like aggregated data with revenue
    if data and len(data) > 0:
        first_row = data[0]
        keys = list(first_row.keys())
        
        # Simple bar chart for revenue data
        if 'total_revenue' in keys or 'revenue' in keys:
            revenue_key = 'total_revenue' if 'total_revenue' in keys else 'revenue'
            label_key = next((k for k in keys if k not in [revenue_key, 'id']), keys[0])
            
            return {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Query Results",
                "data": {"values": data[:20]},  # Limit to 20 for visualization
                "mark": "bar",
                "encoding": {
                    "x": {"field": label_key, "type": "nominal", "sort": "-y"},
                    "y": {"field": revenue_key, "type": "quantitative"},
                    "tooltip": [
                        {"field": label_key, "type": "nominal"},
                        {"field": revenue_key, "type": "quantitative", "format": ",.2f"}
                    ]
                }
            }
    
    return {}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message and return SQL analysis results.
    """
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    message = request.message.strip()
    
    # Route intent to get SQL or follow-up questions
    intent_result = route_intent(message)
    sql = intent_result.get("sql")
    follow_ups = intent_result.get("follow_up_questions", [])
    assumptions = intent_result.get("assumptions", [])
    
    # If no SQL generated, return follow-up questions
    if sql is None:
        runtime_ms = int((time.time() - start_time) * 1000)
        
        # Audit log for clarification needed
        insert_audit_log(
            session_id=session_id,
            question=message,
            sql_text=None,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text="Needs clarification"
        )
        
        return ChatResponse(
            answer="I need more information to help you. Could you please clarify your question?",
            sql=None,
            assumptions=[],
            chart=ChartSpec(vega_lite_spec={}),
            follow_up_questions=follow_ups,
            metadata=ChatMetadata(row_count=0, runtime_ms=runtime_ms)
        )
    
    # Validate SQL with guardrails
    try:
        validated_sql = validate_sql(sql)
    except SQLPolicyError as e:
        runtime_ms = int((time.time() - start_time) * 1000)
        
        # Audit log for policy violation
        insert_audit_log(
            session_id=session_id,
            question=message,
            sql_text=sql,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text=f"SQL Policy Violation: {str(e)}"
        )
        
        return ChatResponse(
            answer=f"I couldn't execute that query due to a safety policy: {str(e)}",
            sql=sql,
            assumptions=assumptions,
            chart=ChartSpec(vega_lite_spec={}),
            follow_up_questions=["Could you rephrase your question?", "Would you like to try a different analysis?"],
            metadata=ChatMetadata(row_count=0, runtime_ms=runtime_ms)
        )
    
    # Execute SQL
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(validated_sql))
            rows = result.fetchall()
            columns = result.keys()
            
            # Convert to list of dicts
            data = [dict(zip(columns, row)) for row in rows]
            row_count = len(data)
        
        runtime_ms = int((time.time() - start_time) * 1000)
        
        # Generate chart spec
        vega_spec = generate_vega_lite_spec(data, validated_sql)
        
        # Generate answer based on results
        if row_count == 0:
            answer = "The query returned no results."
        elif row_count == 1:
            answer = f"Found 1 result. {_format_single_result(data[0])}"
        else:
            answer = f"Found {row_count} results. {_format_summary(data, validated_sql)}"
        
        # Audit log for successful query
        insert_audit_log(
            session_id=session_id,
            question=message,
            sql_text=validated_sql,
            runtime_ms=runtime_ms,
            row_count=row_count,
            error_text=None
        )
        
        return ChatResponse(
            answer=answer,
            sql=validated_sql,
            assumptions=assumptions,
            chart=ChartSpec(vega_lite_spec=vega_spec),
            follow_up_questions=_generate_follow_ups(validated_sql),
            metadata=ChatMetadata(row_count=row_count, runtime_ms=runtime_ms)
        )
        
    except Exception as e:
        runtime_ms = int((time.time() - start_time) * 1000)
        
        # Audit log for execution error
        insert_audit_log(
            session_id=session_id,
            question=message,
            sql_text=validated_sql,
            runtime_ms=runtime_ms,
            row_count=0,
            error_text=f"Execution Error: {str(e)}"
        )
        
        return ChatResponse(
            answer=f"An error occurred while executing the query: {str(e)}",
            sql=validated_sql,
            assumptions=assumptions,
            chart=ChartSpec(vega_lite_spec={}),
            follow_up_questions=["Could you try a different question?", "Would you like to see available data tables?"],
            metadata=ChatMetadata(row_count=0, runtime_ms=runtime_ms)
        )


def _format_single_result(row: Dict) -> str:
    """Format a single result row into a readable string."""
    parts = [f"{k}: {v}" for k, v in row.items()]
    return ", ".join(parts)


def _format_summary(data: List[Dict], sql: str) -> str:
    """Generate a summary of the results."""
    if not data:
        return ""
    
    first_row = data[0]
    
    # Check for revenue aggregation
    if 'total_revenue' in first_row:
        top_item = data[0]
        name_key = next((k for k in first_row.keys() if k not in ['total_revenue', 'id']), None)
        if name_key:
            return f"Top result: {top_item.get(name_key)} with ${top_item.get('total_revenue', 0):,.2f} in revenue."
    
    return f"Showing the first {min(len(data), 10)} of {len(data)} results."


def _generate_follow_ups(sql: str) -> List[str]:
    """Generate relevant follow-up questions based on the executed SQL."""
    follow_ups = []
    
    sql_lower = sql.lower()
    
    if 'product' in sql_lower:
        follow_ups.append("Would you like to see revenue by territory?")
        follow_ups.append("Show me the sales trend for the top product")
    elif 'territory' in sql_lower:
        follow_ups.append("Which products perform best in each territory?")
        follow_ups.append("Show me the top HCPs by territory")
    elif 'sales' in sql_lower:
        follow_ups.append("What are the top products by revenue?")
        follow_ups.append("Show me revenue trends by month")
    
    if not follow_ups:
        follow_ups = [
            "What are the top products by revenue?",
            "Show me revenue by territory"
        ]
    
    return follow_ups[:3]
