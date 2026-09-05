"""Spec2Tests FastAPI application entry point.

Creates and configures the FastAPI application instance: CORS middleware,
routers, and top-level health/metadata endpoints. Run locally with:

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import documents, generate_test_cases, generation

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Application factory that builds and configures the FastAPI instance."""
    if not settings.gemini_api_key.strip():
        logger.warning(
            "GEMINI_API_KEY is not set. Test case generation endpoints will be "
            "unavailable until a valid Gemini API key is configured."
        )

    application = FastAPI(
        title=settings.app_name,
        description=(
            "Spec2Tests backend API: upload software specification documents "
            "and generate structured test cases powered by Google Gemini."
        ),
        version="0.1.0",
        debug=settings.debug,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/", tags=["health"])
    async def root() -> dict[str, str]:
        """Basic service liveness/metadata endpoint."""
        return {
            "service": settings.app_name,
            "status": "ok",
            "environment": settings.app_env,
        }

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Health-check endpoint used by uptime probes and orchestrators."""
        return {"status": "ok"}

    application.include_router(documents.router)
    application.include_router(generation.router)
    application.include_router(generate_test_cases.router)

    return application


app = create_app()
