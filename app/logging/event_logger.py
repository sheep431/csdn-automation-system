from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import LOG_DIR


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLogger:
    def __init__(self, log_file: Path | None = None) -> None:
        self.log_file = log_file or (LOG_DIR / "events.jsonl")

    def log(
        self,
        *,
        task_id: str,
        article_id: str,
        level: str,
        stage: str,
        action: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "timestamp": utc_now_iso(),
            "task_id": task_id,
            "article_id": article_id,
            "level": level,
            "stage": stage,
            "action": action,
            "message": message,
            "extra": extra or {},
        }
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def info(
        self,
        *,
        task_id: str,
        article_id: str,
        stage: str,
        action: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.log(
            task_id=task_id,
            article_id=article_id,
            level="INFO",
            stage=stage,
            action=action,
            message=message,
            extra=extra,
        )

    def warning(
        self,
        *,
        task_id: str,
        article_id: str,
        stage: str,
        action: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.log(
            task_id=task_id,
            article_id=article_id,
            level="WARNING",
            stage=stage,
            action=action,
            message=message,
            extra=extra,
        )

    def error(
        self,
        *,
        task_id: str,
        article_id: str,
        stage: str,
        action: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.log(
            task_id=task_id,
            article_id=article_id,
            level="ERROR",
            stage=stage,
            action=action,
            message=message,
            extra=extra,
        )
