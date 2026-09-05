"""Integration tests for ``POST /api/generate-test-cases`` (BRD-mandatory).

Exercises the multipart/form-data endpoint that accepts a mandatory BRD
file, an optional FRD file, and optional free-text context, concatenates
their extracted text into a single specification prompt, and returns a
raw JSON array of test case objects. Only the outermost Gemini SDK
boundary (``genai.GenerativeModel``) is mocked; extraction runs for real
against in-memory fixture bytes.
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

import app.services.gemini_service as gemini_service
from tests.conftest import make_pdf_bytes

ENDPOINT = "/api/generate-test-cases"

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


def _fake_response(text: str):
    return SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason=None),
        candidates=[SimpleNamespace()],
        text=text,
    )


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
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    from app.config import get_settings

    get_settings.cache_clear()
    yield


BRD_TEXT = (
    "Business Requirements Document. The system shall allow a registered user "
    "to reset a forgotten password by requesting a reset link sent to their "
    "registered email address."
)
FRD_TEXT = (
    "Functional Requirements Document. The reset link shall expire after 24 "
    "hours and display a clear error when reused after expiry."
)


class TestBrdMandatoryEnforcement:
    def test_missing_brd_file_returns_400_with_mandatory_message(self, client):
        response = client.post(ENDPOINT, data={"context": "some context"})

        assert response.status_code == 400
        body = response.json()
        assert "BRD file is mandatory" in body["detail"]

    def test_missing_brd_with_only_frd_still_returns_400(self, client, mocker):
        frd_bytes = make_pdf_bytes([FRD_TEXT])
        _patch_model(mocker, response=_fake_response(text=json.dumps([VALID_TEST_CASE])))

        response = client.post(
            ENDPOINT,
            files={"frd_file": ("frd.pdf", io.BytesIO(frd_bytes), "application/pdf")},
        )

        assert response.status_code == 400
        assert "BRD file is mandatory" in response.json()["detail"]


class TestBrdOnlySuccess:
    def test_brd_only_request_succeeds_and_returns_raw_json_array(
        self, client, mocker, configured_api_key
    ):
        brd_bytes = make_pdf_bytes([BRD_TEXT])
        _patch_model(mocker, response=_fake_response(text=json.dumps([VALID_TEST_CASE])))

        response = client.post(
            ENDPOINT,
            files={"brd_file": ("brd.pdf", io.BytesIO(brd_bytes), "application/pdf")},
        )

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        case = body[0]
        # 7 content fields (plus server-assigned id) matching the schema.
        for field in (
            "id",
            "requirement_reference",
            "title",
            "description",
            "preconditions",
            "steps",
            "expected_result",
            "priority",
            "type",
        ):
            assert field in case
        assert case["title"] == VALID_TEST_CASE["title"]
        assert case["id"] == "TC-001"
        # The blueprint's required "Requirement Reference" column must be
        # populated (non-null) on every generated test case.
        assert case["requirement_reference"] is not None
        assert case["requirement_reference"] == VALID_TEST_CASE["requirement_reference"]

        for tc in body:
            assert tc["requirement_reference"] is not None


class TestBrdFrdContextConcatenation:
    def test_brd_frd_and_context_are_all_concatenated_into_prompt(
        self, client, mocker, configured_api_key
    ):
        brd_bytes = make_pdf_bytes([BRD_TEXT])
        frd_bytes = make_pdf_bytes([FRD_TEXT])
        _patch_model(mocker, response=_fake_response(text=json.dumps([VALID_TEST_CASE])))

        import app.routers.generate_test_cases as generate_test_cases_router

        spy = mocker.spy(generate_test_cases_router, "generate_test_cases")

        response = client.post(
            ENDPOINT,
            data={"context": "Extra context: rate-limit password reset requests."},
            files={
                "brd_file": ("brd.pdf", io.BytesIO(brd_bytes), "application/pdf"),
                "frd_file": ("frd.pdf", io.BytesIO(frd_bytes), "application/pdf"),
            },
        )

        assert response.status_code == 200
        assert spy.call_count == 1
        sent_spec_text = spy.call_args.kwargs["specification_text"]
        assert "reset a forgotten password" in sent_spec_text
        assert "expire after 24" in sent_spec_text
        assert "rate-limit password reset requests" in sent_spec_text


class TestInvalidFileExtension:
    def test_unsupported_brd_extension_returns_400(self, client):
        response = client.post(
            ENDPOINT,
            files={
                "brd_file": (
                    "brd.rtf",
                    io.BytesIO(b"{\\rtf1 unsupported}"),
                    "application/rtf",
                )
            },
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_unsupported_frd_extension_returns_400(self, client, mocker, configured_api_key):
        brd_bytes = make_pdf_bytes([BRD_TEXT])
        _patch_model(mocker, response=_fake_response(text=json.dumps([VALID_TEST_CASE])))

        response = client.post(
            ENDPOINT,
            files={
                "brd_file": ("brd.pdf", io.BytesIO(brd_bytes), "application/pdf"),
                "frd_file": ("frd.rtf", io.BytesIO(b"{\\rtf1 unsupported}"), "application/rtf"),
            },
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


class TestGeminiFailureTranslatedTo502:
    def test_gemini_failure_returns_502(self, client, mocker, configured_api_key):
        brd_bytes = make_pdf_bytes([BRD_TEXT])
        _patch_model(mocker, response=_fake_response(text="not valid json at all"))

        response = client.post(
            ENDPOINT,
            files={"brd_file": ("brd.pdf", io.BytesIO(brd_bytes), "application/pdf")},
        )

        assert response.status_code == 502
        assert "could not be parsed" in response.json()["detail"]
