"""Pydantic schemas describing extracted document data.

These models define the response contract for the document extraction
endpoint: the plain-text content pulled out of an uploaded specification
document (PDF, DOCX, or TXT) plus metadata useful to downstream consumers
(e.g. the test-case generation service).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedDocument(BaseModel):
    """Result of successfully extracting text from an uploaded document."""

    filename: str = Field(..., description="Original filename of the uploaded document.")
    extension: str = Field(
        ..., description="Lower-cased file extension detected from the filename (e.g. '.pdf')."
    )
    content_type: str = Field(
        ..., description="Resolved MIME type of the source document."
    )
    text: str = Field(..., description="Extracted, whitespace-normalised plain text content.")
    character_count: int = Field(
        ..., ge=0, description="Number of characters in the extracted text."
    )
    word_count: int = Field(..., ge=0, description="Number of whitespace-delimited words extracted.")
    page_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Number of pages in the source document, when applicable "
            "(populated for PDF documents; null otherwise)."
        ),
    )
    paragraph_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Number of non-empty paragraphs extracted, when applicable "
            "(populated for DOCX documents; null otherwise)."
        ),
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues encountered while extracting text (e.g. empty pages).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "filename": "requirements.pdf",
                "extension": ".pdf",
                "content_type": "application/pdf",
                "text": "1. Introduction\nThe system shall allow users to...",
                "character_count": 1024,
                "word_count": 168,
                "page_count": 3,
                "paragraph_count": None,
                "warnings": [],
            }
        }
    }


class ExtractionErrorResponse(BaseModel):
    """Standardised error payload returned when extraction fails."""

    detail: str = Field(..., description="Human-readable description of the failure.")
    error_code: str = Field(
        ..., description="Machine-readable error identifier for client-side handling."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "Unsupported file type: '.xlsx'. Allowed types: .pdf, .docx, .txt",
                "error_code": "unsupported_file_type",
            }
        }
    }
