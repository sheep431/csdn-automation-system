from __future__ import annotations

from app.config import MAX_RETRIES
from app.publishers.csdn_publisher import (
    CaptchaRequiredError,
    EditorNotReadyError,
    LoginExpiredError,
    PublisherError,
    ResultUncertainError,
)


class RetryPolicy:
    def __init__(self, max_retries: int = MAX_RETRIES) -> None:
        self.max_retries = max_retries

    def should_retry(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False

        if isinstance(exc, (CaptchaRequiredError, LoginExpiredError, ResultUncertainError)):
            return False

        if isinstance(exc, EditorNotReadyError):
            return True

        if isinstance(exc, PublisherError):
            message = str(exc).lower()
            retry_markers = [
                "timeout",
                "temporarily",
                "network",
                "detached",
                "closed",
            ]
            return any(marker in message for marker in retry_markers)

        return False
