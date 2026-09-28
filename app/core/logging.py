"""Logging setup for the application's own loggers (the ``app`` package).

Uvicorn configures its own loggers; this only takes care of ours, so that
LOG_LEVEL controls what the service writes without touching third parties.
"""
import logging

APP_LOGGER_NAME = "app"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str) -> None:
    """Set ``level`` on the application logger and make sure it has one handler."""
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    app_logger.setLevel(level)

    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        app_logger.addHandler(handler)
