"""Unit tests for ``app.services.gemini_service``.

All Gemini SDK interactions are mocked (``genai.GenerativeModel``) so these
tests run deterministically, offline, and without ever making a real network
call to Google's API. Coverage includes: the happy path, missing API key,
transport/SDK failures, blocked/empty responses, malformed JSON, partial
validation failures, code-fence stripping, alternate response shapes, and
`max_test_cases` truncation with sequential ID re-assignment.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from google.api_core import exceptions as google_api_exceptions

import app.services.gemini_service as gemini_service
from app.services.gemini_service import (
    EmptyGenerationError,
    GeminiNotConfiguredError,
    GeminiRequestError,
    GeminiResponseParsingError,
    generate_test_cases,
)

VALID_TEST_CASE = {
    "id": "TC-999",
    "requirement_reference": "BRD-1.1",
    "title": "User can log in with valid credentials",
    "description": "Verifies successful authentication with valid credentials.",
    "preconditions": ["A registered user account exists."],
    "steps": ["Navigate to the login page.", "Enter valid credentials.", "Submit the form."],
    "expected_result": "The user is authenticated and redirected to the dashboard.",
    "priority": "High",
    "type": "Functional",
}


def _fake_response(
    text: str | None = None,
    has_candidates: bool = True,
    block_reason: str | None = None,
    text_raises: Exception | None = None,
):
    """Build a lightweight stand-in for ``GenerateContentResponse``."""

    class _FakeResponse:
        def __init__(self):
            self.prompt_feedback = SimpleNamespace(block_reason=block_reason)
            self.candidates = [SimpleNamespace()] if has_candidates else []

        @property
        def text(self):
            if text_raises is not None:
                raise text_raises
            return text

    return _FakeResponse()


@pytest.fixture()
def configured_api_key(monkeypatch):
    """Ensure a non-empty Gemini API key is present for the test's duration."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    from app.config import get_settings

    get_settings.cache_clear()
    yield "test-api-key-123"


def _patch_model(mocker, response=None, side_effect=None):
    """Patch ``genai.GenerativeModel`` to return a mock with a controlled response."""
    mock_model_instance = mocker.Mock()
    if side_effect is not None:
        mock_model_instance.generate_content.side_effect = side_effect
    else:
        mock_model_instance.generate_content.return_value = response

    mock_model_class = mocker.patch.object(
        gemini_service.genai, "GenerativeModel", return_value=mock_model_instance
    )
    return mock_model_class, mock_model_instance


class TestGenerateTestCasesHappyPath:
    def test_returns_structured_test_cases_from_valid_json_array(
        self, mocker, configured_api_key
    ):
        raw_json = json.dumps([VALID_TEST_CASE])
        _patch_model(mocker, response=_fake_response(text=raw_json))

        test_cases, warnings = generate_test_cases(
            specification_text="The system shall allow users to log in.",
            max_test_cases=10,
            filename="spec.txt",
        )

        assert warnings == []
        assert len(test_cases) == 1
        case = test_cases[0]
        assert case.id == "TC-001"  # sequential IDs are always reassigned
        assert case.requirement_reference == VALID_TEST_CASE["requirement_reference"]
        assert case.title == VALID_TEST_CASE["title"]
        assert case.description == VALID_TEST_CASE["description"]
        assert case.steps == VALID_TEST_CASE["steps"]
        assert case.priority.value == "High"
        assert case.type.value == "Functional"

    def test_strips_markdown_code_fences_from_response_text(self, mocker, configured_api_key):
        fenced = "```json\n" + json.dumps([VALID_TEST_CASE]) + "\n```"
        _patch_model(mocker, response=_fake_response(text=fenced))

        test_cases, warnings = generate_test_cases("Some specification text here.")

        assert len(test_cases) == 1
        assert warnings == []

    def test_tolerates_wrapped_object_with_test_cases_key(self, mocker, configured_api_key):
        wrapped = json.dumps({"test_cases": [VALID_TEST_CASE]})
        _patch_model(mocker, response=_fake_response(text=wrapped))

        test_cases, warnings = generate_test_cases("Some specification text here.")

        assert len(test_cases) == 1
        assert test_cases[0].id == "TC-001"

    def test_reassigns_sequential_ids_regardless_of_model_output(
        self, mocker, configured_api_key
    ):
        first = {**VALID_TEST_CASE, "id": "weird-id-a"}
        second = {**VALID_TEST_CASE, "id": "weird-id-a", "title": "Second case"}
        _patch_model(mocker, response=_fake_response(text=json.dumps([first, second])))

        test_cases, _ = generate_test_cases("Some specification text here.")

        assert [tc.id for tc in test_cases] == ["TC-001", "TC-002"]

    def test_truncates_results_to_max_test_cases(self, mocker, configured_api_key):
        items = [{**VALID_TEST_CASE, "title": f"Case {i}"} for i in range(5)]
        _patch_model(mocker, response=_fake_response(text=json.dumps(items)))

        test_cases, warnings = generate_test_cases(
            "Some specification text here.", max_test_cases=2
        )

        assert len(test_cases) == 2
        assert [tc.id for tc in test_cases] == ["TC-001", "TC-002"]

    def test_coerces_single_string_preconditions_and_steps_to_lists(
        self, mocker, configured_api_key
    ):
        item = {
            **VALID_TEST_CASE,
            "preconditions": "A single precondition string.",
            "steps": "A single step string.",
        }
        _patch_model(mocker, response=_fake_response(text=json.dumps([item])))

        test_cases, warnings = generate_test_cases("Some specification text here.")

        assert test_cases[0].preconditions == ["A single precondition string."]
        assert test_cases[0].steps == ["A single step string."]
        assert warnings == []


class TestGenerateTestCasesConfigurationErrors:
    def test_raises_not_configured_error_when_api_key_missing(self, monkeypatch, mocker):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from app.config import get_settings

        get_settings.cache_clear()

        mock_model_class = mocker.patch.object(gemini_service.genai, "GenerativeModel")

        with pytest.raises(GeminiNotConfiguredError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert exc_info.value.error_code == "gemini_not_configured"
        assert "GEMINI_API_KEY" in exc_info.value.message
        mock_model_class.assert_not_called()


class TestGenerateTestCasesRequestErrors:
    def test_raises_request_error_on_google_api_call_error(self, mocker, configured_api_key):
        _patch_model(
            mocker, side_effect=google_api_exceptions.ServiceUnavailable("upstream is down")
        )

        with pytest.raises(GeminiRequestError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert exc_info.value.error_code == "gemini_request_failed"

    def test_raises_request_error_on_unexpected_exception(self, mocker, configured_api_key):
        _patch_model(mocker, side_effect=RuntimeError("boom"))

        with pytest.raises(GeminiRequestError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert exc_info.value.error_code == "gemini_request_failed"

    def test_raises_request_error_when_response_blocked_by_safety_filter(
        self, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(block_reason="SAFETY"))

        with pytest.raises(GeminiRequestError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert "blocked" in exc_info.value.message
        assert exc_info.value.error_code == "gemini_request_failed"

    def test_raises_request_error_when_no_candidates_returned(
        self, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(text="[]", has_candidates=False))

        with pytest.raises(GeminiRequestError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert "no candidates" in exc_info.value.message

    def test_raises_request_error_when_response_text_is_blank(self, mocker, configured_api_key):
        _patch_model(mocker, response=_fake_response(text="   "))

        with pytest.raises(GeminiRequestError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert "did not contain any usable text content" in exc_info.value.message

    def test_raises_request_error_when_text_property_raises(self, mocker, configured_api_key):
        _patch_model(mocker, response=_fake_response(text_raises=ValueError("blocked content")))

        with pytest.raises(GeminiRequestError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert "did not contain any usable text content" in exc_info.value.message


class TestGenerateTestCasesParsingErrors:
    def test_raises_parsing_error_for_invalid_json(self, mocker, configured_api_key):
        _patch_model(mocker, response=_fake_response(text="this is not json at all"))

        with pytest.raises(GeminiResponseParsingError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert exc_info.value.error_code == "gemini_response_invalid"

    def test_raises_parsing_error_when_json_is_not_a_list_or_recognised_object(
        self, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(text=json.dumps({"foo": "bar"})))

        with pytest.raises(GeminiResponseParsingError):
            generate_test_cases("Some specification text here.")

    def test_raises_parsing_error_when_json_is_a_scalar(self, mocker, configured_api_key):
        _patch_model(mocker, response=_fake_response(text=json.dumps("just a string")))

        with pytest.raises(GeminiResponseParsingError):
            generate_test_cases("Some specification text here.")


class TestGenerateTestCasesEmptyResult:
    def test_raises_empty_generation_error_for_empty_json_array(
        self, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(text="[]"))

        with pytest.raises(EmptyGenerationError) as exc_info:
            generate_test_cases("Some specification text here.")

        assert exc_info.value.error_code == "no_test_cases_generated"

    def test_raises_empty_generation_error_when_all_items_are_malformed(
        self, mocker, configured_api_key
    ):
        malformed = [{"not": "a valid test case shape"}, "not even an object"]
        _patch_model(mocker, response=_fake_response(text=json.dumps(malformed)))

        with pytest.raises(EmptyGenerationError):
            generate_test_cases("Some specification text here.")

    def test_skips_invalid_items_but_keeps_valid_ones_with_warnings(
        self, mocker, configured_api_key
    ):
        items = [VALID_TEST_CASE, {"not": "a valid test case shape"}, "not even an object"]
        _patch_model(mocker, response=_fake_response(text=json.dumps(items)))

        test_cases, warnings = generate_test_cases("Some specification text here.")

        assert len(test_cases) == 1
        assert len(warnings) == 2
