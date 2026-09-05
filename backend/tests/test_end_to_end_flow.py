"""End-to-end integration test covering the full Spec2Tests user flow.

Simulates exactly what a real client does: upload a specification document
to ``/api/documents/extract``, take the extracted text from that response,
and feed it into ``/api/generate/test-cases`` to obtain structured test
cases. Only the outermost Gemini SDK boundary is mocked; every other layer
(FastAPI routing, request/response validation, the real extraction service,
the real generation service's parsing/validation logic) executes for real.
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

import app.services.gemini_service as gemini_service
from tests.conftest import make_pdf_bytes

GENERATED_TEST_CASES = [
    {
        "id": "ignored-by-server",
        "title": "User can register with a valid email and password",
        "description": (
            "Verifies that a new user can create an account by supplying a valid, "
            "unique email address and a password meeting the minimum length policy."
        ),
        "preconditions": ["The email address is not already registered."],
        "steps": [
            "Navigate to the registration page.",
            "Enter a unique email address and a password of at least 8 characters.",
            "Submit the registration form.",
        ],
        "expected_result": "The account is created and the user is redirected to the login page.",
        "priority": "High",
        "type": "Functional",
    },
    {
        "id": "ignored-by-server-2",
        "title": "Registration is rejected when the password is too short",
        "description": (
            "Verifies that the system enforces the minimum password length during "
            "registration and surfaces a clear validation error."
        ),
        "preconditions": [],
        "steps": [
            "Navigate to the registration page.",
            "Enter a valid email address and a password shorter than 8 characters.",
            "Submit the registration form.",
        ],
        "expected_result": (
            "Registration is rejected and an error message about the password "
            "length requirement is displayed."
        ),
        "priority": "Medium",
        "type": "Negative",
    },
]


def _fake_response(text: str):
    return SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason=None),
        candidates=[SimpleNamespace()],
        text=text,
    )


@pytest.fixture()
def configured_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    from app.config import get_settings

    get_settings.cache_clear()
    yield


class TestFullUploadThenGenerateFlow:
    def test_uploaded_pdf_specification_flows_through_to_generated_test_cases(
        self, client, mocker, configured_api_key
    ):
        # Step 1: a real specification document is uploaded and its text extracted.
        specification_prose = (
            "User Registration Requirements. The system shall allow a new user to "
            "register an account by providing a unique email address and a password "
            "that is at least 8 characters long. If the password does not meet the "
            "minimum length, the system shall reject the registration and display a "
            "validation error message to the user."
        )
        pdf_bytes = make_pdf_bytes([specification_prose])

        extract_response = client.post(
            "/api/documents/extract",
            files={"file": ("registration_spec.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        assert extract_response.status_code == 200
        extracted = extract_response.json()
        assert "register an account" in extracted["text"]
        assert extracted["character_count"] > 0

        # Step 2: the extracted text is fed directly into the generation endpoint,
        # exactly as a real client would chain the two calls.
        mocker.patch.object(
            gemini_service.genai,
            "GenerativeModel",
            return_value=mocker.Mock(
                generate_content=mocker.Mock(
                    return_value=_fake_response(json.dumps(GENERATED_TEST_CASES))
                )
            ),
        )

        generate_response = client.post(
            "/api/generate/test-cases",
            json={
                "specification_text": extracted["text"],
                "filename": extracted["filename"],
                "max_test_cases": 10,
            },
        )

        assert generate_response.status_code == 200
        generated = generate_response.json()

        # Response shape and traceability back to the source document.
        assert generated["source_filename"] == "registration_spec.pdf"
        assert generated["model"] == "gemini-3.6-flash"
        assert generated["generated_count"] == 2
        assert generated["warnings"] == []

        # Server-assigned, sequential, collision-free IDs regardless of model output.
        test_case_ids = [tc["id"] for tc in generated["test_cases"]]
        assert test_case_ids == ["TC-001", "TC-002"]

        # The actual generated content is present and well-formed end to end.
        positive_case = generated["test_cases"][0]
        assert positive_case["title"] == "User can register with a valid email and password"
        assert positive_case["priority"] == "High"
        assert positive_case["type"] == "Functional"
        assert len(positive_case["steps"]) == 3

        negative_case = generated["test_cases"][1]
        assert negative_case["type"] == "Negative"
        assert "password" in negative_case["description"].lower()

    def test_flow_surfaces_generation_failure_after_successful_extraction(
        self, client, mocker, configured_api_key
    ):
        """Extraction succeeding does not guarantee generation succeeds.

        A downstream Gemini failure must still be surfaced to the caller with
        the documented 502 status and a human-readable detail message, even
        though the upstream extraction step completed successfully.
        """
        pdf_bytes = make_pdf_bytes(["The system shall support password resets via email."])

        extract_response = client.post(
            "/api/documents/extract",
            files={"file": ("spec.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert extract_response.status_code == 200
        extracted_text = extract_response.json()["text"]

        mocker.patch.object(
            gemini_service.genai,
            "GenerativeModel",
            return_value=mocker.Mock(
                generate_content=mocker.Mock(
                    return_value=_fake_response("not valid json at all")
                )
            ),
        )

        generate_response = client.post(
            "/api/generate/test-cases",
            json={"specification_text": extracted_text},
        )

        assert generate_response.status_code == 502
        body = generate_response.json()
        assert "could not be parsed" in body["detail"]
