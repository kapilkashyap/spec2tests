"""Additional integration tests for the ``/api/generate/test-cases`` endpoint.

Complements ``test_generation_router.py`` (which covers the endpoint's
happy paths, request validation, and service-error mapping in depth) by
focusing on:

- The ``app.routers.generate`` re-export alias itself, ensuring it exposes
  the exact same router/endpoint object as ``app.routers.generation`` and
  is never mounted a second time by the running application.
- A realistic end-to-end request built from one of the on-disk fixture
  specification documents (mirroring how a real client would feed
  previously extracted text into this endpoint).
- Response schema/content details not otherwise exercised: multiple test
  cases of different types/priorities, warnings surfaced for partially
  invalid model output, and truncation via ``max_test_cases``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.services.gemini_service as gemini_service
from app.routers import generate as generate_alias_module
from app.routers import generation as generation_module

ENDPOINT = "/api/generate/test-cases"

FIXTURES_DIR = Path(__file__).parent / "fixtures"

VALID_SPEC_TEXT = (
    "The system shall allow a registered user to reset a forgotten password "
    "by requesting a reset link sent to their registered email address. The "
    "reset link shall expire after 24 hours, and attempting to use an "
    "expired link shall display a clear error message instructing the user "
    "to request a new one."
)


def _test_case(**overrides) -> dict:
    base = {
        "id": "TC-000",
        "title": "Base test case title",
        "description": "Base test case description explaining intent.",
        "preconditions": ["A precondition."],
        "steps": ["Step one.", "Step two."],
        "expected_result": "The expected outcome occurs.",
        "priority": "Medium",
        "type": "Functional",
    }
    base.update(overrides)
    return base


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
    """Ensure a Gemini API key is configured for the duration of the test."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-123")
    from app.config import get_settings

    get_settings.cache_clear()
    yield


class TestGenerateRouterAliasModule:
    """Verifies the ``app.routers.generate`` naming-convenience alias.

    ``app.main`` mounts ``app.routers.generation.router`` directly; this
    module exists purely so importers can also reach the same objects via
    ``app.routers.generate``. These tests guard against that contract
    silently breaking (e.g. the alias diverging from the real module, or a
    second ``APIRouter`` accidentally being constructed and registered,
    which would duplicate the ``/api/generate/test-cases`` route).
    """

    def test_alias_router_is_the_same_object_as_the_real_router(self):
        assert generate_alias_module.router is generation_module.router

    def test_alias_endpoint_function_is_the_same_object(self):
        assert (
            generate_alias_module.generate_test_cases_endpoint
            is generation_module.generate_test_cases_endpoint
        )

    def test_route_is_registered_exactly_once_on_the_real_application(self):
        from app.main import app

        matching_routes = [
            route
            for route in app.routes
            if getattr(route, "path", None) == "/api/generate/test-cases"
        ]

        assert len(matching_routes) == 1


class TestGenerateEndpointWithFixtureSpecification:
    """Exercises the endpoint using text drawn from an on-disk fixture file.

    This mirrors the realistic client workflow of extracting a document
    first, then submitting its text for generation, without depending on
    the ``/api/documents/extract`` endpoint itself (that flow is already
    covered by ``test_end_to_end_flow.py``).
    """

    def test_generates_test_cases_from_sample_txt_fixture_content(
        self, client, mocker, configured_api_key
    ):
        specification_text = (FIXTURES_DIR / "sample.txt").read_text(encoding="utf-8")

        items = [
            _test_case(
                title="User can register with a unique email and valid password",
                description="Verifies successful registration with valid, unique inputs.",
                type="Functional",
                priority="High",
            ),
            _test_case(
                title="Account locks after five consecutive failed login attempts",
                description="Verifies the brute-force lockout policy is enforced.",
                type="Security",
                priority="High",
            ),
        ]
        _patch_model(mocker, response=_fake_response(text=json.dumps(items)))

        response = client.post(
            ENDPOINT,
            json={
                "specification_text": specification_text,
                "filename": "sample.txt",
                "max_test_cases": 10,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["source_filename"] == "sample.txt"
        assert body["model"] == "gemini-3.6-flash"
        assert body["generated_count"] == 2
        assert body["warnings"] == []

        titles = [tc["title"] for tc in body["test_cases"]]
        assert "User can register with a unique email and valid password" in titles
        assert "Account locks after five consecutive failed login attempts" in titles

        security_case = next(tc for tc in body["test_cases"] if tc["type"] == "Security")
        assert security_case["priority"] == "High"
        assert security_case["id"].startswith("TC-")


class TestGenerateEndpointResponseDetails:
    def test_warnings_surface_when_some_generated_items_are_invalid(
        self, client, mocker, configured_api_key
    ):
        items = [
            _test_case(title="A perfectly valid case"),
            {"title": "Missing required fields entirely"},
            "not even an object",
        ]
        _patch_model(mocker, response=_fake_response(text=json.dumps(items)))

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 200
        body = response.json()
        assert body["generated_count"] == 1
        assert len(body["test_cases"]) == 1
        assert body["test_cases"][0]["title"] == "A perfectly valid case"
        assert len(body["warnings"]) == 2

    def test_result_is_truncated_to_requested_max_test_cases(
        self, client, mocker, configured_api_key
    ):
        items = [_test_case(title=f"Case number {i}") for i in range(8)]
        _patch_model(mocker, response=_fake_response(text=json.dumps(items)))

        response = client.post(
            ENDPOINT,
            json={"specification_text": VALID_SPEC_TEXT, "max_test_cases": 3},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["generated_count"] == 3
        assert len(body["test_cases"]) == 3
        assert [tc["id"] for tc in body["test_cases"]] == ["TC-001", "TC-002", "TC-003"]

    def test_response_content_type_is_json(self, client, mocker, configured_api_key):
        _patch_model(mocker, response=_fake_response(text=json.dumps([_test_case()])))

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

    def test_missing_optional_filename_is_returned_as_null(
        self, client, mocker, configured_api_key
    ):
        _patch_model(mocker, response=_fake_response(text=json.dumps([_test_case()])))

        response = client.post(ENDPOINT, json={"specification_text": VALID_SPEC_TEXT})

        assert response.status_code == 200
        assert response.json()["source_filename"] is None


class TestGenerateEndpointAdditionalValidation:
    def test_returns_422_with_field_level_error_details_for_missing_body(
        self, client, configured_api_key
    ):
        response = client.post(ENDPOINT, json={})

        assert response.status_code == 422
        body = response.json()
        assert "detail" in body
        error_fields = {error["loc"][-1] for error in body["detail"]}
        assert "specification_text" in error_fields

    def test_returns_422_when_request_body_is_not_json(self, client, configured_api_key):
        response = client.post(
            ENDPOINT,
            content=b"specification_text=not-json",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 422

    def test_rejects_max_test_cases_below_minimum(self, client, configured_api_key):
        response = client.post(
            ENDPOINT,
            json={"specification_text": VALID_SPEC_TEXT, "max_test_cases": 0},
        )

        assert response.status_code == 422
