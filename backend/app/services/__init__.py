"""Business logic and integration services for the Spec2Tests backend."""

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
from app.services.gemini_service import (
    EmptyGenerationError,
    GeminiNotConfiguredError,
    GeminiRequestError,
    GeminiResponseParsingError,
    GeminiServiceError,
    generate_test_cases,
)

__all__ = [
    "CorruptedDocumentError",
    "DocumentExtractionError",
    "EmptyFileUploadError",
    "EncryptedDocumentError",
    "FileTooLargeError",
    "NoExtractableTextError",
    "UnsupportedFileTypeError",
    "extract_document",
    "EmptyGenerationError",
    "GeminiNotConfiguredError",
    "GeminiRequestError",
    "GeminiResponseParsingError",
    "GeminiServiceError",
    "generate_test_cases",
]
