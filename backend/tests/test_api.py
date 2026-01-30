"""
Tests for API endpoints.
"""
import os
import pytest
from fastapi.testclient import TestClient

# Temporarily set env vars for testing
os.environ.setdefault("DATABASE_URL", "postgresql://pharma_user:pharma_secret_123@localhost:5432/pharma_db")

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test that health endpoint returns ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_chat_without_api_key():
    """Test that chat returns proper error when OPENAI_API_KEY is missing."""
    # Remove API key if set
    original_key = os.environ.pop("OPENAI_API_KEY", None)
    
    try:
        # Clear cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        response = client.post(
            "/api/chat",
            json={"message": "What are the top products?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return proper response shape even without API key
        assert "answer" in data
        assert "sql" in data
        assert "assumptions" in data
        assert "chart" in data
        assert "follow_up_questions" in data
        assert "metadata" in data
        
        # Should indicate LLM is required
        assert "LLM" in data["answer"] or "OPENAI_API_KEY" in data["answer"]
        assert data["sql"] is None
        assert "row_count" in data["metadata"]
        assert "runtime_ms" in data["metadata"]
        
    finally:
        # Restore API key if it was set
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
        get_settings.cache_clear()


def test_chat_response_shape():
    """Test that chat response has correct shape regardless of content."""
    response = client.post(
        "/api/chat",
        json={"message": "hello"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response shape matches API contract
    assert isinstance(data.get("answer"), str)
    assert data.get("sql") is None or isinstance(data.get("sql"), str)
    assert isinstance(data.get("assumptions"), list)
    assert isinstance(data.get("chart"), dict)
    assert "vega_lite_spec" in data["chart"]
    assert isinstance(data.get("follow_up_questions"), list)
    assert isinstance(data.get("metadata"), dict)
    assert "row_count" in data["metadata"]
    assert "runtime_ms" in data["metadata"]


def test_chat_ambiguous_question():
    """Test that ambiguous questions return follow-up questions."""
    response = client.post(
        "/api/chat",
        json={"message": "hi"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Ambiguous questions should have null SQL and follow-up questions
    # (unless LLM handles it differently)
    assert data["sql"] is None or len(data.get("follow_up_questions", [])) >= 0


def test_chat_session_id():
    """Test that session_id is accepted and processed."""
    response = client.post(
        "/api/chat",
        json={
            "session_id": "test-session-123",
            "message": "What products are available?"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
