"""API routes for uploading and extracting text from specification documents."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.document import ExtractedDocument
from app.services.extraction import (
    CorruptedDocumentError,
    DocumentExtractionError,
    EmptyFileUploadError,
    EncryptedDocumentError,
    FileTooLargeError,
    NoExtractableTextError,
    UnsupportedFileTypeError,
    extract_document,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Maps domain-specific extraction errors to appropriate HTTP status codes.
_ERROR_STATUS_MAP: dict[type[DocumentExtractionError], int] = {
    UnsupportedFileTypeError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    EmptyFileUploadError: status.HTTP_400_BAD_REQUEST,
    FileTooLargeError: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    CorruptedDocumentError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    EncryptedDocumentError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    NoExtractableTextError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _status_for(error: DocumentExtractionError) -> int:
    """Resolve the HTTP status code for a given extraction error instance."""
    return _ERROR_STATUS_MAP.get(type(error), status.HTTP_422_UNPROCESSABLE_ENTITY)


@router.post(
    "/extract",
    response_model=ExtractedDocument,
    status_code=status.HTTP_200_OK,
    summary="Extract text content from an uploaded specification document",
    responses={
        400: {"description": "The uploaded file is missing or empty."},
        413: {"description": "The uploaded file exceeds the configured size limit."},
        415: {"description": "The uploaded file type is not supported."},
        422: {"description": "The document could not be parsed or contains no usable text."},
    },
)
async def extract_document_text(
    file: UploadFile = File(  # noqa: B008 - idiomatic FastAPI dependency-injection pattern
        ..., description="The specification document to extract text from."
    ),
) -> ExtractedDocument:
    """Accept an uploaded document (PDF, DOCX, or TXT) and return its extracted text.

    The extracted text is normalised (consistent line endings, collapsed
    whitespace) and returned along with lightweight metadata (page/paragraph
    counts, word/character counts, non-fatal warnings) that downstream
    services can use when generating test cases.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename was provided with the uploaded file.",
        )

    file_bytes = await file.read()

    try:
        extracted = extract_document(
            filename=file.filename,
            file_bytes=file_bytes,
            declared_content_type=file.content_type,
        )
    except DocumentExtractionError as exc:
        logger.info(
            "Document extraction failed for '%s': %s (%s)",
            file.filename,
            exc.message,
            exc.error_code,
        )
        raise HTTPException(status_code=_status_for(exc), detail=exc.message) from exc
    finally:
        await file.close()

    return extracted
