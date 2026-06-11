import logging
import sys

from pythonjsonlogger import jsonlogger
from app.core.config import settings

class LudexisJsonFormatter(jsonlogger.JsonFormatter):
    def process_log_record(self, log_record):
        # Remove noisy/default fields we don't currently use
        log_record.pop("taskName", None)
        log_record.pop("processName", None)
        log_record.pop("threadName", None)
        return super().process_log_record(log_record)


def setup_logging() -> None:
    level = getattr(
        logging,
        settings.LOG_LEVEL.upper(),
        logging.INFO,
    )
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    formatter = LudexisJsonFormatter(
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
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)