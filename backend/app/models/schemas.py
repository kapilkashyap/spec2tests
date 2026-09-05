"""Unified Pydantic schema surface for the Spec2Tests backend.

This module is the single, canonical import point for every request and
response schema used across the API. Individual schemas are defined in
focused, feature-specific modules (``app.models.document`` for document
extraction, ``app.models.generation`` for AI-powered test case generation)
and re-exported here so that routers, services, and tests can depend on one
stable namespace — ``app.models.schemas`` — without needing to know which
underlying module a given model happens to live in.

Example:
    >>> from app.models.schemas import (
    ...     ExtractedDocument,
    ...     GenerateTestCasesRequest,
    ...     GenerateTestCasesResponse,
    ...     TestCase,
    ... )
"""

from __future__ import annotations

from app.models.document import ExtractedDocument, ExtractionErrorResponse
from app.models.generation import (
    DEFAULT_TEST_CASES,
    MAX_TEST_CASES,
    MIN_SPECIFICATION_LENGTH,
    MIN_TEST_CASES,
    GenerateTestCasesRequest,
    GenerateTestCasesResponse,
    GenerationErrorResponse,
    TestCase,
    TestCasePriority,
    TestCaseType,
)

__all__ = [
    # Document extraction schemas (app.models.document)
    "ExtractedDocument",
    "ExtractionErrorResponse",
    # Test case generation schemas (app.models.generation)
    "DEFAULT_TEST_CASES",
    "MAX_TEST_CASES",
    "MIN_TEST_CASES",
    "MIN_SPECIFICATION_LENGTH",
    "GenerateTestCasesRequest",
    "GenerateTestCasesResponse",
    "GenerationErrorResponse",
    "TestCase",
    "TestCasePriority",
    "TestCaseType",
]
