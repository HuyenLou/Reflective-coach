"""Tests for session API endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns API info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Reflective Coaching Agent"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_session_requires_valid_max_turns(client: AsyncClient):
    """Test session creation validates max_turns bounds."""
    # Too low
    response = await client.post(
        "/sessions",
        json={"max_turns": 2}
    )
    assert response.status_code == 422

    # Too high
    response = await client.post(
        "/sessions",
        json={"max_turns": 50}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_session(client: AsyncClient):
    """Test getting a session that doesn't exist returns 404."""
    response = await client.get("/sessions/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_message_to_nonexistent_session(client: AsyncClient):
    """Test sending message to nonexistent session returns 404."""
    response = await client.post(
        "/sessions/nonexistent-id/messages",
        json={"content": "Hello"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_end_nonexistent_session(client: AsyncClient):
    """Test ending nonexistent session returns 404."""
    response = await client.post("/sessions/nonexistent-id/end")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_reflection_for_nonexistent_session(client: AsyncClient):
    """Test getting reflection for nonexistent session returns 404."""
    response = await client.get("/sessions/nonexistent-id/reflection")
    assert response.status_code == 404


# Integration tests with mocked LLM
@pytest.mark.asyncio
async def test_create_session_with_topic(client: AsyncClient):
    """Test creating a session with a topic."""
    with patch("app.services.coaching.generate_coach_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "What's on your mind today? Tell me more about wanting to speak up in meetings."

        response = await client.post(
            "/sessions",
            json={
                "topic": "I want to speak up more in meetings",
                "max_turns": 12
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["phase"] == "framing"
        assert data["max_turns"] == 12
        assert data["turn_count"] == 0
        assert data["turns_remaining"] == 12
        assert "content" in data


@pytest.mark.asyncio
async def test_create_session_without_topic(client: AsyncClient):
    """Test creating a session without a topic uses default greeting."""
    with patch("app.services.coaching.generate_coach_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "What brings you to this conversation today?"

        response = await client.post(
            "/sessions",
            json={"max_turns": 10}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["phase"] == "framing"
        assert data["max_turns"] == 10


@pytest.mark.asyncio
async def test_full_conversation_flow(client: AsyncClient):
    """Test a complete conversation flow from start to reflection."""
    with patch("app.services.coaching.generate_coach_response", new_callable=AsyncMock) as mock_coach:
        with patch("app.core.agent.generate_coach_response", new_callable=AsyncMock) as mock_agent:
            with patch("app.services.reflection.generate_reflection", new_callable=AsyncMock) as mock_reflect:
                # Setup mocks
                mock_coach.return_value = "What's on your mind today?"
                mock_agent.return_value = "Tell me more about that."
                mock_reflect.return_value = {
                    "key_observations": "The learner showed courage in exploring their fears.",
                    "outcome_classification": "partial_progress",
                    "insights_summary": "Increased awareness of pattern.",
                    "commitment": None,
                    "suggested_followup": "Continue exploration in next session."
                }

                # Create session
                create_response = await client.post(
                    "/sessions",
                    json={"topic": "Test topic", "max_turns": 6}
                )
                assert create_response.status_code == 201
                session_id = create_response.json()["session_id"]

                # Get session details
                get_response = await client.get(f"/sessions/{session_id}")
                assert get_response.status_code == 200
                assert get_response.json()["session_id"] == session_id
