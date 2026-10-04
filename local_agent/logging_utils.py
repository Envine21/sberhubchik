"""Структурированное логирование событий harness."""
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from local_agent.diagnostics import clean

# Префикс для отличия логов от обычного вывода
_LOG_PREFIX = "[harness-log]"
# Максимальная длина строкового значения в логе
_MAX_VALUE_LEN = 200


def _truncate(value):
    """Сократить длинное строковое значение."""
    if not isinstance(value, str):
        return value
    if len(value) <= _MAX_VALUE_LEN:
        return value
    return value[: _MAX_VALUE_LEN - 3] + "..."


def _sanitize(value):
    """Скрыть секреты и сократить значение."""
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return _truncate(clean(str(value)))


class RunLogger:
    """Логгер одного запуска harness с уникальным run_id."""

    def __init__(self, stream=None):
        self.run_id = uuid.uuid4().hex[:12]
        self._stream = stream or sys.stdout
        self._started_at = time.monotonic()

    def log(self, stage, status, step=None, call_id=None, duration_ms=None, **extra):
        """Записать одно событие в формате JSON."""
        event = {
            "run_id": self.run_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "status": status,
        }
        if step is not None:
            event["step"] = step
        if call_id is not None:
            event["call_id"] = call_id
        if duration_ms is not None:
            event["duration_ms"] = round(duration_ms, 2)
        for key, value in extra.items():
            event[key] = _sanitize(value)

        line = f"{_LOG_PREFIX} {json.dumps(event, ensure_ascii=False)}"
        try:
            self._stream.write(line + "\n")
            self._stream.flush()
        except Exception:
            # Логгер не должен ломать основную программу
            pass

    def elapsed_ms(self):
        return (time.monotonic() - self._started_at) * 1000