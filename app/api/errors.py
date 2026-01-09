"""Custom exceptions and error handlers for the API."""

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi import Request


class CoachingException(Exception):
    """Base exception for coaching application."""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class SessionNotFoundError(CoachingException):
    """Raised when a session is not found."""
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session {session_id} not found",
            error_code="SESSION_NOT_FOUND"
        )


class SessionAlreadyEndedError(CoachingException):
    """Raised when trying to interact with an ended session."""
    def __init__(self, session_id: str, status: str):
        super().__init__(
            message=f"Session {session_id} is already {status}",
            error_code="SESSION_ALREADY_ENDED"
        )


class EmptyMessageError(CoachingException):
    """Raised when message content is empty."""
    def __init__(self):
        super().__init__(
            message="Message content cannot be empty",
            error_code="EMPTY_MESSAGE"
        )


class LLMError(CoachingException):
    """Raised when LLM call fails."""
    def __init__(self, detail: str = "LLM service unavailable"):
        super().__init__(
            message=detail,
            error_code="LLM_ERROR"
        )


class ReflectionNotFoundError(CoachingException):
    """Raised when reflection is not found for a session."""
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Reflection not found for session {session_id}",
            error_code="REFLECTION_NOT_FOUND"
        )


# =============================================================================
# Exception Handlers
# =============================================================================

async def session_not_found_handler(request: Request, exc: SessionNotFoundError):
    """Handle SessionNotFoundError."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": exc.message,
            "error_code": exc.error_code
        }
    )


async def session_already_ended_handler(request: Request, exc: SessionAlreadyEndedError):
    """Handle SessionAlreadyEndedError."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": exc.message,
            "error_code": exc.error_code
        }
    )


async def empty_message_handler(request: Request, exc: EmptyMessageError):
    """Handle EmptyMessageError."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": exc.message,
            "error_code": exc.error_code
        }
    )


async def llm_error_handler(request: Request, exc: LLMError):
    """Handle LLMError."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": exc.message,
            "error_code": exc.error_code
        }
    )


async def reflection_not_found_handler(request: Request, exc: ReflectionNotFoundError):
    """Handle ReflectionNotFoundError."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": exc.message,
            "error_code": exc.error_code
        }
    )


def register_exception_handlers(app):
    """Register all custom exception handlers with the FastAPI app."""
    app.add_exception_handler(SessionNotFoundError, session_not_found_handler)
    app.add_exception_handler(SessionAlreadyEndedError, session_already_ended_handler)
    app.add_exception_handler(EmptyMessageError, empty_message_handler)
    app.add_exception_handler(LLMError, llm_error_handler)
    app.add_exception_handler(ReflectionNotFoundError, reflection_not_found_handler)
