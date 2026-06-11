import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.config import settings

def setup_logging() -> None:
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
    )
    handler.setFormatter(formatter)
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)