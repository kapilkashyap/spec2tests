"""BRD-mandatory multipart test case generation endpoint.

Implements ``POST /api/generate-test-cases``: a single multipart/form-data
endpoint that accepts a mandatory Business Requirements Document (``brd_file``),
an optional Functional Requirements Document (``frd_file``), and optional
free-text ``context``. The text extracted from each supplied document (plus
the raw context) is concatenated into one specification prompt and handed to
:func:`app.services.gemini_service.generate_test_cases`.

This complements (and does not replace) the existing two-step workflow
(``POST /api/documents/extract`` followed by ``POST /api/generate/test-cases``)
by offering callers a single round-trip that also enforces the BRD-mandatory
business rule directly at the API boundary.

Response contract: a **raw JSON array** of test case objects (not wrapped in
an envelope object), matching :class:`~app.models.generation.TestCase`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.models.generation import TestCase
from app.services.extraction import (
    DocumentExtractionError,
    UnsupportedFileTypeError,
    extract_document,
)
from app.services.gemini_service import GeminiServiceError, generate_test_cases

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])

BRD_MANDATORY_MESSAGE = (
    "BRD file is mandatory. Please upload a Business Requirements Document "
    "(.pdf, .docx, or .txt) to generate test cases."
)


def _extract_text_or_400(file: UploadFile, file_bytes: bytes, role: str) -> str:
    """Extract text from an uploaded document, translating failures to HTTP 400.

    Args:
        file: The uploaded file (used for its filename/content-type).
        file_bytes: The raw bytes already read from ``file``.
        role: Human-readable label ("BRD" or "FRD") used in error messages.

    Raises:
        HTTPException: With status 400 if the file type is unsupported or the
            document cannot otherwise be extracted (empty, corrupted, etc.).
    """
    try:
        extracted = extract_document(
            filename=file.filename or "",
            file_bytes=file_bytes,
            declared_content_type=file.content_type,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except DocumentExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not process {role} file '{file.filename}': {exc.message}",
        ) from exc
    return extracted.text


def _build_combined_specification(
    brd_text: str, frd_text: str | None, context: str | None
) -> str:
    """Concatenate BRD, optional FRD, and optional free-text context into one prompt."""
    sections = ["=== Business Requirements Document (BRD) ===", brd_text]
    if frd_text:
        sections.append("=== Functional Requirements Document (FRD) ===")
        sections.append(frd_text)
    if context and context.strip():
        sections.append("=== Additional Context ===")
        sections.append(context.strip())
    return "\n\n".join(sections)


@router.post(
    "/api/generate-test-cases",
    response_model=list[TestCase],
    status_code=status.HTTP_200_OK,
    summary="Generate test cases from a mandatory BRD plus optional FRD and context",
    responses={
        400: {"description": "BRD file missing, or an uploaded file is unsupported/unreadable."},
        502: {"description": "The Gemini API request failed or returned an unparsable response."},
    },
)
async def generate_test_cases_from_documents(
    brd_file: UploadFile | None = File(  # noqa: B008 - idiomatic FastAPI dependency-injection pattern
        default=None,
        description="Mandatory Business Requirements Document (.pdf, .docx, or .txt).",
    ),
    frd_file: UploadFile | None = File(  # noqa: B008 - idiomatic FastAPI dependency-injection pattern
        default=None,
        description="Optional Functional Requirements Document (.pdf, .docx, or .txt).",
    ),
    context: str | None = Form(
        default=None,
        description="Optional free-text additional context to include in the prompt.",
    ),
) -> list[TestCase]:
    """Generate structured test cases from an uploaded BRD (mandatory) and optional FRD/context.

    Returns a raw JSON array of test case objects (7 content fields plus a
    server-assigned ``id``) derived from the combined specification text.
    """
    if brd_file is None or not brd_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=BRD_MANDATORY_MESSAGE)

    brd_bytes = await brd_file.read()
    brd_text = _extract_text_or_400(brd_file, brd_bytes, role="BRD")

    frd_text: str | None = None
    if frd_file is not None and frd_file.filename:
        frd_bytes = await frd_file.read()
        frd_text = _extract_text_or_400(frd_file, frd_bytes, role="FRD")

    specification_text = _build_combined_specification(brd_text, frd_text, context)

    try:
        test_cases, _warnings = generate_test_cases(
            specification_text=specification_text,
            filename=brd_file.filename,
        )
    except GeminiServiceError as exc:
        logger.info(
            "Test case generation failed for BRD '%s': %s (%s)",
            brd_file.filename,
            exc.message,
            exc.error_code,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc

    return test_cases
