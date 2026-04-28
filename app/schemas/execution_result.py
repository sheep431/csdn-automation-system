from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.schemas.enums import ErrorType, ExecutionStage, PublishMode, TaskStatus


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionResult(BaseModel):
    task_id: str
    article_id: str
    status: TaskStatus
    final_stage: ExecutionStage
    publish_mode: PublishMode

    retry_count: int = 0
    error_type: ErrorType | None = None
    error_message: str | None = None
    manual_reason: str | None = None

    draft_url: str | None = None
    article_url: str | None = None

    screenshot_path: str | None = None
    snapshot_path: str | None = None

    started_at: str = Field(default_factory=utc_now_iso)
    ended_at: str | None = None
    duration_ms: int | None = None

    @classmethod
    def started(
        cls,
        task_id: str,
        article_id: str,
        publish_mode: PublishMode,
    ) -> "ExecutionResult":
        return cls(
            task_id=task_id,
            article_id=article_id,
            status=TaskStatus.RUNNING,
            final_stage=ExecutionStage.INIT,
            publish_mode=publish_mode,
        )

    def finish(
        self,
        status: TaskStatus,
        final_stage: ExecutionStage,
        error_type: ErrorType | None = None,
        error_message: str | None = None,
        manual_reason: str | None = None,
        draft_url: str | None = None,
        article_url: str | None = None,
        screenshot_path: str | None = None,
        snapshot_path: str | None = None,
    ) -> None:
        self.status = status
        self.final_stage = final_stage
        self.error_type = error_type
        self.error_message = error_message
        self.manual_reason = manual_reason
        self.draft_url = draft_url
        self.article_url = article_url
        self.screenshot_path = screenshot_path
        self.snapshot_path = snapshot_path
        self.ended_at = utc_now_iso()
        self.duration_ms = self._calculate_duration_ms()

    def _calculate_duration_ms(self) -> int | None:
        if not self.started_at or not self.ended_at:
            return None

        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.ended_at)
        return int((end - start).total_seconds() * 1000)
