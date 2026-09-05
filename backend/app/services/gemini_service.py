"""Google Gemini integration service for AI-powered test case generation.

Wraps the ``google-generativeai`` SDK to turn extracted specification text
into a structured list of :class:`~app.models.generation.TestCase` objects.

Design notes
------------
- The Gemini client is configured lazily, on first use, so importing this
  module never requires a valid API key (useful for tests that mock the
  client entirely).
- The model is instructed to respond with strict JSON (via
  ``response_mime_type="application/json"``) matching a documented schema,
  which is then parsed and validated through Pydantic. A best-effort
  fallback strips Markdown code fences in case the model does not honour
  the JSON-only instruction.
- All SDK-level failures (network errors, invalid API key, safety blocks,
  quota errors, malformed responses) are normalised into domain-specific
  :class:`GeminiServiceError` subclasses that the API layer maps to HTTP
  responses, mirroring the pattern used by ``app.services.extraction``.
"""

from __future__ import annotations

import json
import logging
import re

import google.generativeai as genai
from google.api_core import exceptions as google_api_exceptions
from pydantic import ValidationError

from app.config import get_settings
from app.models.generation import DEFAULT_TEST_CASES, TestCase

logger = logging.getLogger(__name__)

# Strips ```json ... ``` or ``` ... ``` Markdown code fences that the model
# occasionally wraps its JSON output in, despite being instructed not to.
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

# Generation parameters tuned for deterministic, structured JSON output.
_TEMPERATURE = 0.2
_TOP_P = 0.95
_MAX_OUTPUT_TOKENS = 8192

# JSON Schema describing a single test case object, matching the 7 required
# content fields of `app.models.generation.TestCase` (plus the `id`). Passed
# to Gemini as `response_schema` (alongside `response_mime_type="application/json"`)
# so the model is constrained to emit well-formed, on-schema JSON directly,
# rather than relying solely on prompt instructions.
_TEST_CASE_RESPONSE_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "requirement_reference": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "preconditions": {"type": "array", "items": {"type": "string"}},
            "steps": {"type": "array", "items": {"type": "string"}},
            "expected_result": {"type": "string"},
            "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
            "type": {
                "type": "string",
                "enum": [
                    "Functional",
                    "Negative",
                    "Edge Case",
                    "Integration",
                    "Boundary",
                    "Security",
                    "Performance",
                    "Usability",
                ],
            },
        },
        "required": [
            "id",
            "requirement_reference",
            "title",
            "description",
            "preconditions",
            "steps",
            "expected_result",
            "priority",
            "type",
        ],
    },
}

# Tracks whether `genai.configure` has already been called for the current
# API key, avoiding redundant (but harmless) reconfiguration on every request.
_configured_api_key: str | None = None


class GeminiServiceError(Exception):
    """Base class for all Gemini test-case generation failures.

    Attributes:
        error_code: Stable, machine-readable identifier for the failure
            reason, intended for use in API error responses.
    """

    error_code: str = "generation_failed"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class GeminiNotConfiguredError(GeminiServiceError):
    """Raised when no Gemini API key is configured on the server."""

    error_code = "gemini_not_configured"


class GeminiRequestError(GeminiServiceError):
    """Raised when the request to the Gemini API fails or is blocked."""

    error_code = "gemini_request_failed"


class GeminiResponseParsingError(GeminiServiceError):
    """Raised when the Gemini response cannot be parsed as valid JSON."""

    error_code = "gemini_response_invalid"


class EmptyGenerationError(GeminiServiceError):
    """Raised when Gemini returns zero usable test cases."""

    error_code = "no_test_cases_generated"


def _ensure_configured() -> None:
    """Configure the ``google-generativeai`` client if not already done.

    Raises:
        GeminiNotConfiguredError: If no API key is present in settings.
    """
    global _configured_api_key

    settings = get_settings()
    api_key = settings.gemini_api_key.strip()

    if not api_key:
        raise GeminiNotConfiguredError(
            "The Gemini API key is not configured on the server. Set the "
            "GEMINI_API_KEY environment variable to enable test case generation."
        )

    if _configured_api_key != api_key:
        genai.configure(api_key=api_key)
        _configured_api_key = api_key


def _build_prompt(specification_text: str, max_test_cases: int) -> str:
    """Construct the instruction prompt sent to Gemini.

    The prompt asks for a strict JSON array of test case objects matching
    the :class:`~app.models.generation.TestCase` schema, derived solely from
    the supplied specification text.
    """
    return f"""You are a senior QA engineer. Read the software specification document
below and derive a comprehensive set of test cases that verify its requirements.

Generate at most {max_test_cases} test cases. Prioritise covering distinct
requirements, functional flows, negative/error scenarios, boundary conditions,
and important edge cases over sheer quantity. Do not invent requirements that
are not implied by the specification text.

Respond with ONLY a JSON array (no Markdown, no commentary, no surrounding
text) where each element is an object with exactly this shape:

{{
  "id": "TC-001",
  "requirement_reference": "BRD Section 3.2",
  "title": "Short, descriptive title",
  "description": "What this test case verifies and why it matters",
  "preconditions": ["Condition that must be true before running the test", "..."],
  "steps": ["Step 1", "Step 2", "..."],
  "expected_result": "The expected outcome after performing the steps",
  "priority": "High" | "Medium" | "Low",
  "type": "Functional" | "Negative" | "Edge Case" | "Integration" | "Boundary" | "Security" | "Performance" | "Usability"
}}

Rules:
- "id" values must be unique and formatted as "TC-001", "TC-002", etc., in order.
- "requirement_reference" must identify the specific BRD/FRD clause, section, or
  requirement number this test case validates (e.g. "BRD Section 3.2", "FRD-4.1",
  "REQ-014"). Use the exact numbering/heading found in the specification document
  whenever one is present. If the source document has no explicit requirement
  numbering, make a concise best-effort reference instead (e.g. "BRD - User
  Registration section") rather than leaving it blank.
- "preconditions" and "steps" must always be JSON arrays of strings (never a bare string).
- "steps" must contain at least one concrete, actionable step.
- Every field is required; do not omit any field or use null values.
- Output must be a single valid JSON array and nothing else.

Specification document:
\"\"\"
{specification_text}
\"\"\"
"""


def _strip_code_fences(raw_text: str) -> str:
    """Remove Markdown code fences that may wrap the model's JSON output."""
    return _CODE_FENCE_RE.sub("", raw_text.strip()).strip()


def _extract_response_text(response: genai.types.GenerateContentResponse) -> str:
    """Safely pull the text content out of a Gemini response.

    Raises:
        GeminiRequestError: If the response was blocked or contains no
            candidates/text (e.g. due to safety filtering).
    """
    prompt_feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(prompt_feedback, "block_reason", None)
    if block_reason:
        raise GeminiRequestError(
            f"The Gemini API blocked the request (reason: {block_reason})."
        )

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        raise GeminiRequestError(
            "The Gemini API returned no candidates for the given specification text."
        )

    try:
        text = response.text
    except (ValueError, AttributeError) as exc:
        raise GeminiRequestError(
            "The Gemini API response did not contain any usable text content."
        ) from exc

    if not text or not text.strip():
        raise GeminiRequestError(
            "The Gemini API response did not contain any usable text content."
        )

    return text


def _parse_test_cases_json(raw_text: str) -> list[dict]:
    """Parse the model's raw text output into a list of test case dicts.

    Raises:
        GeminiResponseParsingError: If the text is not valid JSON, or the
            top-level JSON value is not an array.
    """
    cleaned = _strip_code_fences(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse Gemini response as JSON: %s", exc)
        raise GeminiResponseParsingError(
            "The Gemini API returned a response that could not be parsed as valid JSON."
        ) from exc

    if isinstance(parsed, dict):
        # Tolerate a common alternative shape: {"test_cases": [...]}.
        parsed = parsed.get("test_cases", parsed.get("testCases"))

    if not isinstance(parsed, list):
        raise GeminiResponseParsingError(
            "The Gemini API response JSON was not a list of test case objects."
        )

    return parsed


def _coerce_test_cases(raw_items: list[dict], max_test_cases: int) -> tuple[list[TestCase], list[str]]:
    """Validate raw parsed JSON objects into :class:`TestCase` instances.

    Items that fail validation are skipped (with a warning) rather than
    failing the entire request, so a single malformed entry does not
    discard an otherwise-usable set of generated test cases.

    Returns:
        A tuple of ``(test_cases, warnings)``, truncated to ``max_test_cases``.
    """
    test_cases: list[TestCase] = []
    warnings: list[str] = []

    for index, item in enumerate(raw_items):
        if len(test_cases) >= max_test_cases:
            break
        if not isinstance(item, dict):
            warnings.append(f"Skipped malformed test case at position {index}: not an object.")
            continue
        try:
            test_case = TestCase.model_validate(item)
        except ValidationError as exc:
            logger.info("Skipping invalid generated test case at position %d: %s", index, exc)
            warnings.append(
                f"Skipped an invalid test case returned by Gemini at position {index}."
            )
            continue
        test_cases.append(test_case)

    return test_cases, warnings


def _reassign_sequential_ids(test_cases: list[TestCase]) -> list[TestCase]:
    """Re-number test case IDs sequentially (TC-001, TC-002, ...).

    Guards against duplicate or out-of-order IDs returned by the model,
    ensuring the final response always has stable, predictable identifiers.
    """
    renumbered: list[TestCase] = []
    for position, test_case in enumerate(test_cases, start=1):
        renumbered.append(test_case.model_copy(update={"id": f"TC-{position:03d}"}))
    return renumbered


def generate_test_cases(
    specification_text: str,
    max_test_cases: int = DEFAULT_TEST_CASES,
    filename: str | None = None,
) -> tuple[list[TestCase], list[str]]:
    """Generate structured test cases from specification text via Gemini.

    Args:
        specification_text: Extracted plain-text specification content.
        max_test_cases: Upper bound on the number of test cases to return.
        filename: Original source filename, used only for log context.

    Returns:
        A tuple of ``(test_cases, warnings)``.

    Raises:
        GeminiNotConfiguredError: If no API key is configured.
        GeminiRequestError: If the request to Gemini fails or is blocked.
        GeminiResponseParsingError: If the response cannot be parsed as JSON.
        EmptyGenerationError: If parsing succeeds but yields zero valid
            test cases.
    """
    _ensure_configured()
    settings = get_settings()

    prompt = _build_prompt(specification_text, max_test_cases)

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        generation_config=genai.types.GenerationConfig(
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
            response_schema=_TEST_CASE_RESPONSE_SCHEMA,
        ),
    )

    try:
        response = model.generate_content(prompt)
    except google_api_exceptions.GoogleAPICallError as exc:
        logger.error(
            "Gemini API call failed for '%s': %s", filename or "<unnamed>", exc
        )
        raise GeminiRequestError(
            "The request to the Gemini API failed. Please try again shortly."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive catch-all for SDK errors
        logger.error(
            "Unexpected error calling Gemini API for '%s': %s", filename or "<unnamed>", exc
        )
        raise GeminiRequestError(
            "An unexpected error occurred while communicating with the Gemini API."
        ) from exc

    raw_text = _extract_response_text(response)
    raw_items = _parse_test_cases_json(raw_text)
    test_cases, warnings = _coerce_test_cases(raw_items, max_test_cases)

    if not test_cases:
        raise EmptyGenerationError(
            "Gemini did not return any usable test cases for the given specification text."
        )

    test_cases = _reassign_sequential_ids(test_cases)

    return test_cases, warnings
