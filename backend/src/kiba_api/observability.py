"""Small production-safe logging and request-correlation helpers."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Serialize conventional LogRecord fields without request bodies or secrets."""

    def format(self, record: logging.LogRecord) -> str:
        value: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in ("event", "request_id", "method", "path", "status_code", "duration_ms"):
            item = getattr(record, name, None)
            if item is not None:
                value[name] = item
        if record.exc_info:
            value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value, ensure_ascii=False)


def configure_logging(*, json_logs: bool) -> None:
    """Configure the root logger once for local text or production JSON output."""
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    formatter: logging.Formatter = (
        JsonFormatter()
        if json_logs
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    for handler in root.handlers:
        handler.setFormatter(formatter)
    root.setLevel(logging.INFO)
