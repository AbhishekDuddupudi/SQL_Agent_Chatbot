"""
Chat sessions API endpoints.
Handles session CRUD and message history retrieval.
"""
from typing import List, Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import require_auth
from app.services.chat_history import (
    create_session,
    get_user_sessions,
    get_session,
    get_session_messages,
)

router = APIRouter()


# ============ Response Models ============

class SessionResponse(BaseModel):
    id: int
    user_id: int
    title: Optional[str] = None
    created_at: Optional[str]
    updated_at: Optional[str]


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    sql_query: Optional[str] = None
    created_at: Optional[str]


# ============ Endpoints ============

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(request: Request, user: dict = Depends(require_auth)):
    """
    Get all chat sessions for the current user.
    Returns most recent sessions first.
    """
    sessions = get_user_sessions(user["id"])
    return sessions


@router.post("/sessions", response_model=SessionResponse)
async def create_new_session(request: Request, user: dict = Depends(require_auth)):
    """
    Create a new empty chat session.
    Title will be auto-set when first message is sent.
    """
    session = create_session(user["id"])
    return session


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: int,
    request: Request,
    user: dict = Depends(require_auth)
):
    """
    Get all messages for a specific session.
    Verifies that the session belongs to the current user.
    """
    # First verify the session exists and belongs to user
    session = get_session(session_id, user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = get_session_messages(session_id, user["id"])
    return messages
