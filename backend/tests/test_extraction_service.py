"""Unit tests for ``app.services.extraction`` (document text extraction).

Covers the happy path for every supported format (PDF, DOCX, TXT) plus the
domain-specific error conditions the service is documented to raise:
unsupported file types, empty uploads, oversized uploads, corrupted
documents, encrypted PDFs, and documents with no extractable text.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.services.extraction import (
    CorruptedDocumentError,
    EmptyFileUploadError,
    EncryptedDocumentError,
    FileTooLargeError,
    NoExtractableTextError,
    UnsupportedFileTypeError,
    extract_document,
)
from tests.conftest import (
    make_docx_bytes,
    make_empty_docx_bytes,
    make_empty_pdf_bytes,
    make_encrypted_pdf_bytes,
    make_pdf_bytes,
)


class TestExtractPdf:
    def test_extracts_text_and_metadata_from_single_page_pdf(self):
        pdf_bytes = make_pdf_bytes(["The system shall allow users to login securely."])

        result = extract_document("requirements.pdf", pdf_bytes, "application/pdf")

        assert result.filename == "requirements.pdf"
        assert result.extension == ".pdf"
        assert result.content_type == "application/pdf"
        assert "login securely" in result.text
        assert result.page_count == 1
        assert result.paragraph_count is None
        assert result.character_count == len(result.text)
        assert result.word_count == len(result.text.split())
        assert result.warnings == []

    def test_extracts_and_joins_text_from_multi_page_pdf(self):
        pdf_bytes = make_pdf_bytes(
            ["First page requirement text.", "Second page requirement text."]
        )

        result = extract_document("multi.pdf", pdf_bytes)

        assert result.page_count == 2
        assert "First page requirement text." in result.text
        assert "Second page requirement text." in result.text

    def test_infers_content_type_when_not_declared(self):
        pdf_bytes = make_pdf_bytes(["Some content."])

        result = extract_document("spec.pdf", pdf_bytes, declared_content_type=None)

        assert result.content_type == "application/pdf"

    def test_raises_no_extractable_text_for_blank_pdf(self):
        pdf_bytes = make_empty_pdf_bytes()

        with pytest.raises(NoExtractableTextError) as exc_info:
            extract_document("blank.pdf", pdf_bytes)

        assert "blank.pdf" in exc_info.value.message
        assert exc_info.value.error_code == "no_extractable_text"

    def test_raises_encrypted_document_error_for_password_protected_pdf(self):
        pdf_bytes = make_encrypted_pdf_bytes(password="hunter2")

        with pytest.raises(EncryptedDocumentError) as exc_info:
            extract_document("locked.pdf", pdf_bytes)

        assert "password-protected" in exc_info.value.message
        assert exc_info.value.error_code == "encrypted_document"

    def test_raises_corrupted_document_error_for_malformed_pdf_bytes(self):
        garbage = b"%PDF-1.4\nnot a real pdf structure at all" + b"\x00" * 50

        with pytest.raises(CorruptedDocumentError) as exc_info:
            extract_document("broken.pdf", garbage)

        assert exc_info.value.error_code == "corrupted_document"


class TestExtractDocx:
    def test_extracts_paragraphs_and_counts_them(self):
        docx_bytes = make_docx_bytes(
            [
                "The system shall allow users to register with an email and password.",
                "Passwords must be at least eight characters long.",
            ]
        )

        result = extract_document(
            "requirements.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        assert result.extension == ".docx"
        assert result.paragraph_count == 2
        assert result.page_count is None
        assert "register with an email and password" in result.text
        assert "at least eight characters" in result.text

    def test_extracts_table_rows_as_pipe_delimited_lines(self):
        docx_bytes = make_docx_bytes(
            paragraphs=["Field reference table:"],
            table_rows=[["Field", "Type"], ["email", "string"]],
        )

        result = extract_document("with_table.docx", docx_bytes)

        assert "Field | Type" in result.text
        assert "email | string" in result.text

    def test_raises_no_extractable_text_for_empty_docx(self):
        docx_bytes = make_empty_docx_bytes()

        with pytest.raises(NoExtractableTextError):
            extract_document("empty.docx", docx_bytes)

    def test_raises_corrupted_document_error_for_invalid_docx_bytes(self):
        garbage = b"this is not a valid zip/docx package at all"

        with pytest.raises(CorruptedDocumentError) as exc_info:
            extract_document("broken.docx", garbage)

        assert exc_info.value.error_code == "corrupted_document"


class TestExtractTxt:
    def test_extracts_and_normalizes_utf8_text(self):
        raw = "Line one.\r\nLine two.\r\n\r\n\r\n\r\nLine three with   extra   spaces.  \n"

        result = extract_document("notes.txt", raw.encode("utf-8"), "text/plain")

        assert result.extension == ".txt"
        assert result.content_type == "text/plain"
        # CRLF normalised to LF and excess blank lines collapsed to one.
        assert "\r" not in result.text
        assert "\n\n\n" not in result.text
        # Trailing whitespace and intra-line whitespace runs are collapsed.
        assert "Line three with extra spaces." in result.text
        assert result.warnings == []

    def test_decodes_latin1_text_without_raising(self):
        raw = "Café résumé naïve".encode("latin-1")

        result = extract_document("latin1.txt", raw)

        assert "sum" in result.text  # decoded successfully, no crash
        assert result.character_count > 0


class TestExtractDocumentValidation:
    def test_raises_unsupported_file_type_for_unknown_extension(self):
        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            extract_document("spreadsheet.xlsx", b"irrelevant content")

        assert ".xlsx" in exc_info.value.message
        assert exc_info.value.error_code == "unsupported_file_type"

    def test_raises_unsupported_file_type_when_extension_missing(self):
        with pytest.raises(UnsupportedFileTypeError):
            extract_document("no_extension", b"irrelevant content")

    def test_raises_empty_file_error_for_zero_byte_upload(self):
        with pytest.raises(EmptyFileUploadError) as exc_info:
            extract_document("empty.txt", b"")

        assert "empty.txt" in exc_info.value.message
        assert exc_info.value.error_code == "empty_file"

    def test_raises_file_too_large_error_when_exceeding_configured_limit(self, monkeypatch):
        monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
        get_settings.cache_clear()

        oversized = b"a" * (2 * 1024 * 1024)  # 2 MB, exceeds the 1 MB limit above.

        with pytest.raises(FileTooLargeError) as exc_info:
            extract_document("big.txt", oversized)

        assert exc_info.value.error_code == "file_too_large"

    def test_raises_unsupported_file_type_when_extension_not_allowed(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_UPLOAD_EXTENSIONS", ".txt")
        get_settings.cache_clear()

        pdf_bytes = make_pdf_bytes(["Some content."])

        with pytest.raises(UnsupportedFileTypeError):
            extract_document("spec.pdf", pdf_bytes)
