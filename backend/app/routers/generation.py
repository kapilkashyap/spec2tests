"""API routes for generating structured test cases from specification text."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.models.generation import (
    GenerateTestCasesRequest,
    GenerateTestCasesResponse,
)
from app.services.gemini_service import (
    EmptyGenerationError,
    GeminiNotConfiguredError,
    GeminiRequestError,
    GeminiResponseParsingError,
    GeminiServiceError,
    generate_test_cases,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generation"])

# Maps domain-specific generation errors to appropriate HTTP status codes.
_ERROR_STATUS_MAP: dict[type[GeminiServiceError], int] = {
    GeminiNotConfiguredError: status.HTTP_503_SERVICE_UNAVAILABLE,
    GeminiRequestError: status.HTTP_502_BAD_GATEWAY,
    GeminiResponseParsingError: status.HTTP_502_BAD_GATEWAY,
    EmptyGenerationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _status_for(error: GeminiServiceError) -> int:
    """Resolve the HTTP status code for a given generation error instance."""
    return _ERROR_STATUS_MAP.get(type(error), status.HTTP_502_BAD_GATEWAY)


@router.post(
    "/test-cases",
    response_model=GenerateTestCasesResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate structured test cases from specification text using Gemini",
    responses={
        422: {"description": "The request payload is invalid or no test cases could be generated."},
        502: {"description": "The Gemini API request failed or returned an unparsable response."},
        503: {"description": "The Gemini API key is not configured on the server."},
    },
)
async def generate_test_cases_endpoint(
    payload: GenerateTestCasesRequest,
) -> GenerateTestCasesResponse:
    """Accept specification text and return AI-generated, structured test cases.

    The specification text is typically obtained beforehand from
    ``POST /api/documents/extract``, but any sufficiently detailed plain-text
    specification may be supplied directly.
    """
    settings = get_settings()

    try:
        test_cases, warnings = generate_test_cases(
            specification_text=payload.specification_text,
            max_test_cases=payload.max_test_cases,
            filename=payload.filename,
        )
    except GeminiServiceError as exc:
        logger.info(
            "Test case generation failed for '%s': %s (%s)",
            payload.filename or "<unnamed>",
            exc.message,
            exc.error_code,
        )
        raise HTTPException(status_code=_status_for(exc), detail=exc.message) from exc

    return GenerateTestCasesResponse(
        source_filename=payload.filename,
        model=settings.gemini_model,
        test_cases=test_cases,
        generated_count=len(test_cases),
        warnings=warnings,
    )
