"""루트 로깅 구성 — Epic H 구조화(JSON) 모드."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_EXTRA_KEYS = frozenset(
    {
        "request_id",
        "http_method",
        "path",
        "status_code",
        "duration_ms",
    }
)


class JsonLogFormatter(logging.Formatter):
    """한 줄 JSON — 로그 수집기에서 파싱하기 쉬운 형태."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                val = getattr(record, key)
                if val is not None:
                    payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, structured: bool, debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    if structured:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
