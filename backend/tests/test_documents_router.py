"""Integration tests for the ``/api/documents/extract`` endpoint.

Exercises the real FastAPI application (via ``TestClient``, real HTTP-level
request/response handling) together with the real ``extract_document``
service — nothing here is mocked — so these tests give genuine end-to-end
confidence that uploading a document produces the documented response shape
and that every documented error path returns the correct status code and
message.
"""

from __future__ import annotations

import io

from tests.conftest import (
    make_docx_bytes,
    make_empty_pdf_bytes,
    make_encrypted_pdf_bytes,
    make_pdf_bytes,
)

ENDPOINT = "/api/documents/extract"


class TestExtractEndpointHappyPath:
    def test_extracts_text_from_uploaded_pdf(self, client):
        pdf_bytes = make_pdf_bytes(["The system shall allow users to reset their password."])

        response = client.post(
            ENDPOINT,
            files={"file": ("requirements.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["filename"] == "requirements.pdf"
        assert body["extension"] == ".pdf"
        assert body["content_type"] == "application/pdf"
        assert "reset their password" in body["text"]
        assert body["page_count"] == 1
        assert body["paragraph_count"] is None
        assert body["character_count"] == len(body["text"])
        assert body["word_count"] > 0
        assert body["warnings"] == []

    def test_extracts_text_from_uploaded_docx(self, client):
        docx_bytes = make_docx_bytes(
            ["The system shall log all failed login attempts for auditing purposes."]
        )

        response = client.post(
            ENDPOINT,
            files={
                "file": (
                    "requirements.docx",
                    io.BytesIO(docx_bytes),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["extension"] == ".docx"
        assert body["paragraph_count"] == 1
        assert "failed login attempts" in body["text"]

    def test_extracts_text_from_uploaded_txt(self, client):
        content = b"1. Introduction\nThe system shall support two-factor authentication.\n"

        response = client.post(
            ENDPOINT,
            files={"file": ("spec.txt", io.BytesIO(content), "text/plain")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["extension"] == ".txt"
        assert "two-factor authentication" in body["text"]


class TestExtractEndpointErrorHandling:
    def test_returns_415_for_unsupported_file_type(self, client):
        response = client.post(
            ENDPOINT,
            files={
                "file": (
                    "spreadsheet.xlsx",
                    io.BytesIO(b"irrelevant content"),
                    "application/vnd.ms-excel",
                )
            },
        )

        assert response.status_code == 415
        body = response.json()
        assert ".xlsx" in body["detail"]

    def test_returns_400_for_empty_file_upload(self, client):
        response = client.post(
            ENDPOINT,
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        )

        assert response.status_code == 400
        body = response.json()
        assert "empty" in body["detail"].lower()

    def test_returns_422_for_encrypted_pdf(self, client):
        pdf_bytes = make_encrypted_pdf_bytes(password="hunter2")

        response = client.post(
            ENDPOINT,
            files={"file": ("locked.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        assert response.status_code == 422
        body = response.json()
        assert "password-protected" in body["detail"]

    def test_returns_422_for_pdf_with_no_extractable_text(self, client):
        pdf_bytes = make_empty_pdf_bytes()

        response = client.post(
            ENDPOINT,
            files={"file": ("blank.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        assert response.status_code == 422
        body = response.json()
        assert "no extractable text" in body["detail"].lower()

    def test_returns_422_for_corrupted_docx(self, client):
        garbage = b"not a real docx package"

        response = client.post(
            ENDPOINT,
            files={
                "file": (
                    "broken.docx",
                    io.BytesIO(garbage),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

        assert response.status_code == 422
        body = response.json()
        assert "corrupted" in body["detail"].lower() or "not a valid" in body["detail"].lower()

    def test_returns_413_when_file_exceeds_configured_size_limit(self, client, monkeypatch):
        monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
        from app.config import get_settings

        get_settings.cache_clear()

        oversized = b"a" * (2 * 1024 * 1024)

        response = client.post(
            ENDPOINT,
            files={"file": ("big.txt", io.BytesIO(oversized), "text/plain")},
        )

        assert response.status_code == 413
        body = response.json()
        assert "exceeds the maximum" in body["detail"]

    def test_returns_422_when_missing_extension_treated_as_unsupported(self, client):
        response = client.post(
            ENDPOINT,
            files={"file": ("no_extension", io.BytesIO(b"some content"), "text/plain")},
        )

        assert response.status_code == 415
