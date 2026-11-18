"""파이프라인 공용 로깅 설정. 비밀값(API 키)은 로그에 남지 않게 가린다."""

from __future__ import annotations

import logging
import sys


class RedactFilter(logging.Filter):
    """레코드 메시지와 인자에서 비밀값을 [REDACTED]로 바꾼다."""

    def __init__(self, secrets: list[str] | None = None):
        super().__init__()
        self.secrets = [secret for secret in (secrets or []) if secret]

    def add(self, secret: str | None) -> None:
        if secret and secret not in self.secrets:
            self.secrets.append(secret)

    def redact(self, value: str) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        if self.secrets:
            message = self.redact(record.getMessage())
            record.msg, record.args = message, None
            if record.exc_info and record.exc_info[1] is not None:
                record.exc_text = self.redact(logging.Formatter().formatException(record.exc_info))
                record.exc_info = None
        return True


REDACTOR = RedactFilter()


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("pipelines")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
        handler.addFilter(REDACTOR)
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"pipelines.{name}")
