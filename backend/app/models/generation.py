"""Pydantic schemas for AI-powered test case generation.

These models define the request/response contract for the
``/api/generate/test-cases`` endpoint, which turns extracted specification
text into a structured list of test cases using Google Gemini.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator
from app.config import get_settings

# Bounds applied to the caller-supplied `max_test_cases` hint. These keep
# generation requests within a sane range for both cost/latency reasons and
# to avoid degenerate model output.
MIN_TEST_CASES = 1
MAX_TEST_CASES = 50
DEFAULT_TEST_CASES = 10

# Minimum amount of specification text required to attempt generation.
# Extremely short input rarely yields meaningful test cases and is more
# likely to indicate a caller error than a genuine specification.
MIN_SPECIFICATION_LENGTH = 20

settings = get_settings()

class TestCasePriority(str, Enum):
    """Relative importance of a generated test case."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TestCaseType(str, Enum):
    """Category describing the nature/intent of a generated test case."""

    FUNCTIONAL = "Functional"
    NEGATIVE = "Negative"
    EDGE_CASE = "Edge Case"
    INTEGRATION = "Integration"
    BOUNDARY = "Boundary"
    SECURITY = "Security"
    PERFORMANCE = "Performance"
    USABILITY = "Usability"


class TestCase(BaseModel):
    """A single, structured test case derived from a specification document."""

    id: str = Field(
        ..., description="Stable identifier for the test case (e.g. 'TC-001')."
    )
    requirement_reference: str = Field(
        default="",
        description=(
            "Identifier/reference to the specific BRD/FRD requirement this test case "
            "verifies (e.g. 'BRD-3.2' or 'REQ-014')."
        ),
    )
    title: str = Field(..., min_length=1, description="Short, descriptive test case title.")
    description: str = Field(
        ..., min_length=1, description="Summary of what the test case verifies and why."
    )
    preconditions: list[str] = Field(
        default_factory=list,
        description="Conditions or setup required before executing the test steps.",
    )
    steps: list[str] = Field(
        ..., min_length=1, description="Ordered list of actions to execute the test."
    )
    expected_result: str = Field(
        ..., min_length=1, description="The expected outcome after performing the steps."
    )
    priority: TestCasePriority = Field(
        default=TestCasePriority.MEDIUM, description="Relative importance of this test case."
    )
    type: TestCaseType = Field(
        default=TestCaseType.FUNCTIONAL, description="Category describing the test case's intent."
    )

    @field_validator("preconditions", "steps", mode="before")
    @classmethod
    def _coerce_to_list(cls, value: object) -> object:
        """Allow a single string to be provided where a list is expected.

        Gemini's JSON output occasionally collapses a single-item list into
        a bare string; normalising here keeps validation resilient without
        rejecting otherwise-valid generations.
        """
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "TC-001",
                "requirement_reference": "BRD-2.1",
                "title": "User can log in with valid credentials",
                "description": (
                    "Verifies that a registered user can successfully authenticate "
                    "using a valid username and password."
                ),
                "preconditions": ["A registered user account exists."],
                "steps": [
                    "Navigate to the login page.",
                    "Enter a valid username and password.",
                    "Click the 'Log In' button.",
                ],
                "expected_result": (
                    "The user is authenticated and redirected to the dashboard."
                ),
                "priority": "High",
                "type": "Functional",
            }
        }
    }


class GenerateTestCasesRequest(BaseModel):
    """Request payload for generating test cases from specification text."""

    specification_text: str = Field(
        ...,
        min_length=MIN_SPECIFICATION_LENGTH,
        description="Extracted plain-text specification content to generate test cases from.",
    )
    filename: str | None = Field(
        default=None,
        description="Original filename of the source document, used for traceability only.",
    )
    max_test_cases: int = Field(
        default=DEFAULT_TEST_CASES,
        ge=MIN_TEST_CASES,
        le=MAX_TEST_CASES,
        description="Upper bound on the number of test cases to generate.",
    )

    @field_validator("specification_text")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < MIN_SPECIFICATION_LENGTH:
            raise ValueError(
                "specification_text must contain at least "
                f"{MIN_SPECIFICATION_LENGTH} non-whitespace characters."
            )
        return stripped

    model_config = {
        "json_schema_extra": {
            "example": {
                "specification_text": (
                    "1. Introduction\nThe system shall allow users to register an "
                    "account using an email address and password..."
                ),
                "filename": "requirements.pdf",
                "max_test_cases": 10,
            }
        }
    }


class GenerateTestCasesResponse(BaseModel):
    """Result of successfully generating test cases from specification text."""

    source_filename: str | None = Field(
        default=None, description="Original filename of the source document, if provided."
    )
    model: str = Field(..., description="Identifier of the Gemini model used for generation.")
    test_cases: list[TestCase] = Field(
        ..., description="The structured test cases generated from the specification."
    )
    generated_count: int = Field(
        ..., ge=0, description="Number of test cases returned in this response."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues encountered while generating or parsing test cases.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "source_filename": "requirements.pdf",
                "model": settings.gemini_model,
                "test_cases": [
                    {
                        "id": "TC-001",
                        "requirement_reference": "BRD-2.1",
                        "title": "User can log in with valid credentials",
                        "description": (
                            "Verifies that a registered user can successfully "
                            "authenticate using a valid username and password."
                        ),
                        "preconditions": ["A registered user account exists."],
                        "steps": [
                            "Navigate to the login page.",
                            "Enter a valid username and password.",
                            "Click the 'Log In' button.",
                        ],
                        "expected_result": (
                            "The user is authenticated and redirected to the dashboard."
                        ),
                        "priority": "High",
                        "type": "Functional",
                    }
                ],
                "generated_count": 1,
                "warnings": [],
            }
        }
    }


class GenerationErrorResponse(BaseModel):
    """Standardised error payload returned when test case generation fails."""

    detail: str = Field(..., description="Human-readable description of the failure.")
    error_code: str = Field(
        ..., description="Machine-readable error identifier for client-side handling."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "The Gemini API key is not configured on the server.",
                "error_code": "gemini_not_configured",
            }
        }
    }
