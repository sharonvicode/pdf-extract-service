"""Tests for the runtime configuration loaded from environment variables."""
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.main import create_app


class TestSettings:
    def test_ignores_unknown_variables_in_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PORT=9000\nMAX_FILE_SIZE_MB=5\n")

        settings = Settings(_env_file=env_file)

        assert settings.max_file_size_mb == 5

    def test_rejects_invalid_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

        with pytest.raises(ValidationError):
            Settings(_env_file=None)


class TestConfigureLogging:
    @pytest.fixture(autouse=True)
    def restore_app_logger(self):
        app_logger = logging.getLogger("app")
        original_level, original_handlers = app_logger.level, list(app_logger.handlers)
        yield
        app_logger.setLevel(original_level)
        app_logger.handlers = original_handlers

    def test_sets_level_on_the_application_logger(self):
        configure_logging("DEBUG")

        assert logging.getLogger("app").level == logging.DEBUG

    def test_application_logs_are_written_to_a_handler(self):
        configure_logging("INFO")

        assert logging.getLogger("app").handlers

    def test_does_not_duplicate_handlers_when_called_twice(self):
        configure_logging("INFO")
        configure_logging("INFO")

        assert len(logging.getLogger("app").handlers) == 1

    def test_create_app_applies_log_level_from_environment(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        get_settings.cache_clear()
        try:
            create_app()
        finally:
            get_settings.cache_clear()

        assert logging.getLogger("app").level == logging.WARNING
