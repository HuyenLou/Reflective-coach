"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db
from app.api.routes import sessions
from app.api.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    yield
    # Shutdown (cleanup if needed)


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title="Reflective Coaching Agent",
    description="A multi-turn coaching conversation API that surfaces resistance, challenges assumptions, and secures commitments.",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])

# Register exception handlers
register_exception_handlers(app)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Reflective Coaching Agent",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
