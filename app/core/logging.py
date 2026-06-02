import logging
from logging.config import dictConfig
from pathlib import Path


def configure_logging() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "json"},
                "app_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": "logs/app.log",
                    "maxBytes": 10_485_760,
                    "backupCount": 5,
                    "formatter": "json",
                },
                "backup_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": "logs/backup.log",
                    "maxBytes": 10_485_760,
                    "backupCount": 10,
                    "formatter": "json",
                },
            },
            "loggers": {
                "": {"handlers": ["console", "app_file"], "level": "INFO"},
                "backup": {"handlers": ["console", "backup_file"], "level": "INFO", "propagate": False},
            },
        }
    )


app_logger = logging.getLogger("app")
backup_logger = logging.getLogger("backup")
