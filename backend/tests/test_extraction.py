"""Fixture-file-backed tests for ``app.services.extraction``.

Whereas ``test_extraction_service.py`` builds documents in-memory to cover
every branch of the extraction logic in isolation, this module exercises
the same service against real, on-disk fixture files
(``tests/fixtures/sample.pdf``, ``sample.docx``, ``sample.txt``,
``unsupported.rtf``). This gives confidence that the extraction pipeline
behaves correctly against files produced by real authoring tools (or, in
this case, real PDF/DOCX writers) rather than only the minimal synthetic
bytes used by the unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.extraction import (
    EmptyFileUploadError,
    UnsupportedFileTypeError,
    extract_document,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> bytes:
    path = FIXTURES_DIR / name
    return path.read_bytes()


class TestFixtureFilesExist:
    """Guards against the fixtures being accidentally deleted or emptied."""

    @pytest.mark.parametrize(
        "filename",
        ["sample.txt", "sample.docx", "sample.pdf", "unsupported.rtf"],
    )
    def test_fixture_file_exists_and_is_non_empty(self, filename):
        path = FIXTURES_DIR / filename
        assert path.exists(), f"Expected fixture file to exist: {path}"
        assert path.stat().st_size > 0, f"Expected fixture file to be non-empty: {path}"


class TestExtractSampleTxtFixture:
    def test_extracts_expected_content_and_metadata(self):
        file_bytes = _read_fixture("sample.txt")

        result = extract_document("sample.txt", file_bytes, "text/plain")

        assert result.filename == "sample.txt"
        assert result.extension == ".txt"
        assert result.content_type == "text/plain"
        assert result.page_count is None
        assert result.paragraph_count is None
        assert result.warnings == []

        assert "User Account Management" in result.text
        assert "register an account" in result.text
        assert "password reset link via email" in result.text
        assert "Account Lockout" in result.text

        assert result.character_count == len(result.text)
        assert result.word_count == len(result.text.split())
        assert result.character_count > 500

    def test_normalizes_section_separator_lines(self):
        file_bytes = _read_fixture("sample.txt")

        result = extract_document("sample.txt", file_bytes)

        # No excessive (3+) consecutive blank lines should survive normalisation.
        assert "\n\n\n" not in result.text
        # No trailing carriage returns should remain.
        assert "\r" not in result.text


class TestExtractSampleDocxFixture:
    def test_extracts_paragraphs_in_document_order(self):
        file_bytes = _read_fixture("sample.docx")

        result = extract_document(
            "sample.docx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        assert result.extension == ".docx"
        assert result.page_count is None
        assert result.paragraph_count is not None and result.paragraph_count > 0
        assert result.warnings == []

        assert "Spec2Tests Sample Specification" in result.text
        assert "unique email address" in result.text
        assert "authentication error message" in result.text

        # Heading text ("Functional Requirements") should appear before the
        # requirement paragraphs that follow it in the source document.
        heading_index = result.text.index("Functional Requirements")
        registration_index = result.text.index("register an account")
        assert heading_index < registration_index

    def test_extracts_table_content_as_pipe_delimited_rows(self):
        file_bytes = _read_fixture("sample.docx")

        result = extract_document("sample.docx", file_bytes)

        assert "Requirement ID | Description" in result.text
        assert "REQ-001 | User registration with unique email" in result.text
        assert "REQ-002 | Account lockout after 5 failed logins" in result.text


class TestExtractSamplePdfFixture:
    def test_extracts_text_from_all_pages(self):
        file_bytes = _read_fixture("sample.pdf")

        result = extract_document("sample.pdf", file_bytes, "application/pdf")

        assert result.extension == ".pdf"
        assert result.content_type == "application/pdf"
        assert result.paragraph_count is None
        assert result.page_count == 2
        assert result.warnings == []

        assert "Spec2Tests Sample Specification" in result.text
        assert "Page 1: Introduction" in result.text
        assert "Page 2: Functional Requirements" in result.text
        assert "register an account" in result.text

    def test_page_content_is_joined_with_a_blank_line_between_pages(self):
        file_bytes = _read_fixture("sample.pdf")

        result = extract_document("sample.pdf", file_bytes)

        first_page_marker = result.text.index("Page 1: Introduction")
        second_page_marker = result.text.index("Page 2: Functional Requirements")
        assert first_page_marker < second_page_marker

    def test_character_and_word_counts_are_consistent_with_text(self):
        file_bytes = _read_fixture("sample.pdf")

        result = extract_document("sample.pdf", file_bytes)

        assert result.character_count == len(result.text)
        assert result.word_count == len(result.text.split())
        assert result.word_count > 10


class TestExtractUnsupportedRtfFixture:
    def test_raises_unsupported_file_type_error(self):
        file_bytes = _read_fixture("unsupported.rtf")

        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            extract_document("unsupported.rtf", file_bytes, "application/rtf")

        assert ".rtf" in exc_info.value.message
        assert exc_info.value.error_code == "unsupported_file_type"

    def test_rejected_before_any_content_parsing_is_attempted(self):
        """Unsupported types are rejected purely by extension, never parsed.

        Even though ``unsupported.rtf`` contains well-formed RTF markup (not
        plain text), extraction must fail with ``UnsupportedFileTypeError``
        rather than attempting to decode/parse it as one of the supported
        formats and raising a different, misleading error.
        """
        file_bytes = _read_fixture("unsupported.rtf")

        with pytest.raises(UnsupportedFileTypeError):
            extract_document("unsupported.rtf", file_bytes)


class TestCrossFixtureConsistency:
    """Sanity checks that hold across every supported-format fixture."""

    @pytest.mark.parametrize(
        "filename,content_type",
        [
            ("sample.txt", "text/plain"),
            (
                "sample.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            ("sample.pdf", "application/pdf"),
        ],
    )
    def test_supported_fixtures_yield_non_empty_normalised_text(self, filename, content_type):
        file_bytes = _read_fixture(filename)

        result = extract_document(filename, file_bytes, content_type)

        assert result.text.strip() != ""
        assert result.character_count > 0
        assert result.word_count > 0
        # Empty bytes for the same filename always fail distinctly (as an
        # empty upload), never silently succeeding with empty text.
        with pytest.raises(EmptyFileUploadError):
            extract_document(filename, b"")
