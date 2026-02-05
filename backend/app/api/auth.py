"""
Authentication API endpoints.
Handles login, logout, and current user retrieval.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, Cookie
from pydantic import BaseModel, EmailStr

from app.services.auth import (
    authenticate_user,
    create_session,
    delete_session,
    get_session,
    get_user_by_id,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Cookie settings
COOKIE_NAME = "session_id"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    success: bool
    user: Optional[dict] = None
    session_id: Optional[str] = None
    message: str = ""


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str


def get_current_user(request: Request) -> Optional[dict]:
    """
    Helper function to get the current logged-in user from the session cookie.
    Falls back to X-Session-Id header if cookie is missing (dev fallback).
    
    Returns:
        User dict with id, email, display_name, or None if not logged in.
    """
    session_id = request.cookies.get(COOKIE_NAME) or request.headers.get("X-Session-Id")
    
    if not session_id:
        return None
    
    session = get_session(session_id)
    if not session:
        return None
    
    user = get_user_by_id(session["user_id"])
    return user


def require_auth(request: Request) -> dict:
    """
    Dependency that requires authentication.
    Raises 401 if user is not logged in.
    
    Returns:
        User dict with id, email, display_name.
    """
    session_id = request.cookies.get(COOKIE_NAME)
    logger.debug(f"require_auth: session_id cookie = {session_id}")
    logger.debug(f"require_auth: all cookies = {request.cookies}")
    
    user = get_current_user(request)
    
    if not user:
        logger.warning(f"require_auth: No user found for session_id={session_id}")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please log in."
        )
    
    logger.debug(f"require_auth: user authenticated = {user['email']}")
    return user


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    """
    Log in with email and password.
    Sets an httpOnly session cookie on success.
    """
    success, user, error_message = authenticate_user(
        email=request.email,
        password=request.password
    )
    
    if not success or user is None:
        return LoginResponse(
            success=False,
            message=error_message
        )
    
    # Create session and set cookie
    session_id = create_session(user["id"])
    
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,      # Prevent JavaScript access
        samesite="lax",     # CSRF protection
        secure=False,       # Set to True in production with HTTPS
    )
    
    return LoginResponse(
        success=True,
        user=user,
        session_id=session_id,
        message="Login successful"
    )


@router.post("/auth/logout")
async def logout(
    response: Response,
    session_id: Optional[str] = Cookie(None, alias=COOKIE_NAME)
):
    """
    Log out the current user.
    Deletes the session and clears the cookie.
    """
    if session_id:
        delete_session(session_id)
    
    # Clear the cookie
    response.delete_cookie(key=COOKIE_NAME)
    
    return {"success": True, "message": "Logged out successfully"}


@router.get("/auth/me", response_model=Optional[UserResponse])
async def get_me(request: Request):
    """
    Get the current logged-in user.
    Returns null if not logged in (doesn't raise 401).
    """
    user = get_current_user(request)
    
    if not user:
        return None
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"]
    )
