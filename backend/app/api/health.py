"""
Health check endpoint
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns {"status": "ok"} if the service is running.
    """
    return {"status": "ok"}
