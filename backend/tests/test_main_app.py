"""Integration tests for the FastAPI application factory and top-level routes.

Covers ``create_app`` wiring (CORS, router mounting) and the ``/`` and
``/health`` liveness/metadata endpoints defined directly in ``app.main``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


class TestRootAndHealthEndpoints:
    def test_root_endpoint_returns_service_metadata(self, client):
        response = client.get("/")

        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "Spec2Tests"
        assert body["status"] == "ok"
        assert body["environment"] in {"development", "production", "test", "testing"}

    def test_health_endpoint_returns_healthy_status(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCreateAppFactory:
    def test_create_app_builds_independent_app_instances(self):
        app_one = create_app()
        app_two = create_app()

        assert app_one is not app_two
        assert app_one.title == "Spec2Tests"
        assert app_one.version == "0.1.0"

    def test_create_app_mounts_documents_and_generation_routers(self):
        app = create_app()

        route_paths = {route.path for route in app.routes}

        assert "/api/documents/extract" in route_paths
        assert "/api/generate/test-cases" in route_paths

    def test_create_app_configures_cors_middleware(self):
        app = create_app()

        middleware_classes = [m.cls.__name__ for m in app.user_middleware]

        assert "CORSMiddleware" in middleware_classes

    def test_cors_preflight_request_reflects_allowed_origin(self):
        app = create_app()
        test_client = TestClient(app)

        response = test_client.options(
            "/api/documents/extract",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_nonexistent_route_returns_404_with_json_detail(self, client):
        response = client.get("/does-not-exist")

        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
