"""Integration tests for the ``/api/generate/test-cases`` endpoint.

Exercises the real FastAPI application through ``TestClient`` (real HTTP
request/response handling, real Pydantic request validation) while mocking
only the outermost Gemini SDK boundary (``genai.GenerativeModel``), so the
router, error-mapping logic, and response schema are all genuinely tested
end-to-end.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from google.api_core import exceptions as google_api_exceptions

import app.services.gemini_service as gemini_service

ENDPOINT = "/api/generate/test-cases"

VALID_SPEC_TEXT = (
    "The system shall allow a registered user to log in using a valid email "
    "address and password. If the credentials are invalid, the system shall "
    "display an error message and shall not grant access."
)

VALID_TEST_CASE = {
    "id": "TC-001",
    "title": "User can log in with valid credentials",
    "description": "Verifies successful authentication with valid credentials.",
    "preconditions": ["A registered user account exists."],
    "steps": ["Navigate to the login page.", "Enter valid credentials.", "Submit the form."],
    "expected_result": "The user is authenticated and redirected to the dashboard.",
    "priority": "High",
    "type": "Functional",
}


def _fake_response(text: str | None = None, has_candidates: bool = True):
    class _FakeResponse:
        def __init__(self):
            self.prompt_feedback = SimpleNamespace(block_reason=None)
            self.candidates = [SimpleNamespace()] if has_candidates else []
            self.text = text

    return _FakeResponse()


def _patch_model(mocker, response=None, side_effect=None):
    mock_model_instance = mocker.Mock()
    if side_effect is not None:
        mock_model_instance.generate_content.side_effect = side_effect
    else:
        mock_model_instance.generate_content.return_value = response
    return mocker.patch.object(
        gemini_service.genai, "GenerativeModel", return_value=mock_model_instance
    )


@pytest.fixture()
def configured_api_key(monkeypatch):
    """Ensure a Gemini API key is configured for the duration of the test."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    from app.config import get_settings

    get_settings.cache_clear()
    yield


class TestGenerationEndpointHappyPath:
    def test_returns_generated_test_cases_for_valid_specification(
        self, client, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(text=json.dumps([VALID_TEST_CASE])))

        response = client.post(
            ENDPOINT,
            json={
                "specification_text": VALID_SPEC_TEXT,
                "filename": "spec.txt",
                "max_test_cases": 5,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["source_filename"] == "spec.txt"
        assert body["model"] == "gemini-3.6-flash"
        assert body["generated_count"] == 1
        assert body["warnings"] == []
        assert len(body["test_cases"]) == 1
        case = body["test_cases"][0]
        assert case["id"] == "TC-001"
        assert case["title"] == VALID_TEST_CASE["title"]
        assert case["steps"] == VALID_TEST_CASE["steps"]
        assert case["priority"] == "High"
        assert case["type"] == "Functional"

    def test_returns_multiple_test_cases_respecting_default_filename(
        self, client, mocker, configured_api_key
    ):
        items = [
            {**VALID_TEST_CASE, "id": "TC-A", "title": "Case one"},
            {**VALID_TEST_CASE, "id": "TC-B", "title": "Case two"},
        ]
        _patch_model(mocker, response=_fake_response(text=json.dumps(items)))

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 200
        body = response.json()
        assert body["source_filename"] is None
        assert body["generated_count"] == 2
        assert [tc["id"] for tc in body["test_cases"]] == ["TC-001", "TC-002"]
        assert [tc["title"] for tc in body["test_cases"]] == ["Case one", "Case two"]


class TestGenerationEndpointRequestValidation:
    def test_returns_422_when_specification_text_too_short(self, client, configured_api_key):
        response = client.post(ENDPOINT, json={"specification_text": "too short"})

        assert response.status_code == 422

    def test_returns_422_when_specification_text_missing(self, client, configured_api_key):
        response = client.post(ENDPOINT, json={"filename": "spec.txt"})

        assert response.status_code == 422

    def test_returns_422_when_max_test_cases_out_of_bounds(self, client, configured_api_key):
        response = client.post(
            ENDPOINT,
            json={"specification_text": VALID_SPEC_TEXT, "max_test_cases": 500},
        )

        assert response.status_code == 422


class TestGenerationEndpointServiceErrors:
    def test_returns_503_when_gemini_api_key_not_configured(self, client, monkeypatch, mocker):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from app.config import get_settings

        get_settings.cache_clear()
        mock_model_class = mocker.patch.object(gemini_service.genai, "GenerativeModel")

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 503
        body = response.json()
        assert "GEMINI_API_KEY" in body["detail"]
        mock_model_class.assert_not_called()

    def test_returns_502_when_gemini_request_fails(self, client, mocker, configured_api_key):
        _patch_model(
            mocker, side_effect=google_api_exceptions.ServiceUnavailable("upstream is down")
        )

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 502
        body = response.json()
        assert "Gemini API" in body["detail"]

    def test_returns_502_when_gemini_response_is_not_valid_json(
        self, client, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(text="not valid json output"))

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 502
        body = response.json()
        assert "could not be parsed" in body["detail"]

    def test_returns_422_when_gemini_returns_zero_usable_test_cases(
        self, client, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(text="[]"))

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 422
        body = response.json()
        assert "did not return any usable test cases" in body["detail"]
