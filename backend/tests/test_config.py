"""Unit tests for ``app.config`` (environment-driven application settings)."""

from __future__ import annotations

import pytest

from app.config import Settings, _build_settings, _get_bool, _get_list, get_settings


class TestGetBool:
    @pytest.mark.parametrize("raw", ["1", "true", "True", "TRUE", "yes", "YES", "on", "On"])
    def test_returns_true_for_truthy_values(self, monkeypatch, raw):
        monkeypatch.setenv("FLAG", raw)
        assert _get_bool("FLAG", False) is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "garbage", ""])
    def test_returns_false_for_falsy_or_unrecognised_values(self, monkeypatch, raw):
        monkeypatch.setenv("FLAG", raw)
        assert _get_bool("FLAG", True) is False

    def test_returns_default_when_env_var_is_unset(self, monkeypatch):
        monkeypatch.delenv("FLAG", raising=False)
        assert _get_bool("FLAG", True) is True
        assert _get_bool("FLAG", False) is False


class TestGetList:
    def test_splits_comma_separated_values_and_trims_whitespace(self, monkeypatch):
        monkeypatch.setenv("ITEMS", " a, b ,c,, d ")
        assert _get_list("ITEMS", ["default"]) == ["a", "b", "c", "d"]

    def test_returns_default_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("ITEMS", raising=False)
        assert _get_list("ITEMS", ["default1", "default2"]) == ["default1", "default2"]

    def test_returns_default_when_env_var_is_blank(self, monkeypatch):
        monkeypatch.setenv("ITEMS", "   ")
        assert _get_list("ITEMS", ["fallback"]) == ["fallback"]


class TestSettingsValidation:
    def test_normalizes_extensions_to_lowercase_with_leading_dot(self):
        settings = Settings(allowed_upload_extensions=["PDF", ".DOCX", "txt"])
        assert settings.allowed_upload_extensions == [".pdf", ".docx", ".txt"]

    def test_rejects_invalid_log_level(self):
        with pytest.raises(ValueError, match="log_level"):
            Settings(log_level="NOT_A_LEVEL")

    def test_accepts_and_uppercases_valid_log_level(self):
        settings = Settings(log_level="debug")
        assert settings.log_level == "DEBUG"

    def test_max_upload_size_bytes_derives_from_megabyte_setting(self):
        settings = Settings(max_upload_size_mb=5)
        assert settings.max_upload_size_bytes == 5 * 1024 * 1024

    def test_defaults_are_sane_when_constructed_with_no_overrides(self):
        settings = Settings()
        assert settings.app_name == "Spec2Tests"
        assert settings.gemini_model == "gemini-3.6-flash"
        assert settings.allowed_upload_extensions == [".pdf", ".docx", ".txt"]
        assert settings.cors_origins == ["http://localhost:5173", "http://localhost:3000"]


class TestBuildSettingsFromEnvironment:
    def test_reads_overridden_values_from_environment(self, monkeypatch):
        monkeypatch.setenv("APP_NAME", "CustomApp")
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("GEMINI_API_KEY", "my-secret-key")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-pro")
        monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "25")
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com, https://foo.com")
        monkeypatch.setenv("ALLOWED_UPLOAD_EXTENSIONS", ".pdf,.txt")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        settings = _build_settings()

        assert settings.app_name == "CustomApp"
        assert settings.app_env == "production"
        assert settings.debug is False
        assert settings.port == 9000
        assert settings.gemini_api_key == "my-secret-key"
        assert settings.gemini_model == "gemini-3.6-pro"
        assert settings.max_upload_size_mb == 25
        assert settings.cors_origins == ["https://example.com", "https://foo.com"]
        assert settings.allowed_upload_extensions == [".pdf", ".txt"]
        assert settings.log_level == "WARNING"

    def test_falls_back_to_defaults_when_environment_unset(self, monkeypatch):
        for var in (
            "APP_NAME",
            "APP_ENV",
            "DEBUG",
            "PORT",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "MAX_UPLOAD_SIZE_MB",
            "CORS_ORIGINS",
            "ALLOWED_UPLOAD_EXTENSIONS",
            "LOG_LEVEL",
        ):
            monkeypatch.delenv(var, raising=False)

        settings = _build_settings()

        assert settings.app_name == "Spec2Tests"
        assert settings.app_env == "development"
        assert settings.debug is True
        assert settings.port == 8000
        assert settings.gemini_api_key == ""
        assert settings.gemini_model == "gemini-3.6-flash"


class TestGetSettingsCaching:
    def test_returns_same_cached_instance_across_calls(self):
        first = get_settings()
        second = get_settings()
        assert first is second

    def test_reflects_environment_changes_after_cache_clear(self, monkeypatch):
        monkeypatch.setenv("APP_NAME", "FirstName")
        get_settings.cache_clear()
        first = get_settings()
        assert first.app_name == "FirstName"

        monkeypatch.setenv("APP_NAME", "SecondName")
        get_settings.cache_clear()
        second = get_settings()
        assert second.app_name == "SecondName"
