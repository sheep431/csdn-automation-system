from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.schemas.article_task import ArticleTask
from app.schemas.execution_result import ExecutionResult
from app.schemas.enums import PublishMode, TaskStatus


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS article_tasks (
                    task_id TEXT PRIMARY KEY,
                    article_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    publish_mode TEXT NOT NULL,
                    source TEXT,
                    status TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    scheduled_at TEXT,
                    task_payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_article_tasks_article_id "
                "ON article_tasks(article_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_article_tasks_status "
                "ON article_tasks(status)"
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    final_stage TEXT,
                    retry_count INTEGER DEFAULT 0,
                    error_type TEXT,
                    error_message TEXT,
                    manual_reason TEXT,
                    draft_url TEXT,
                    article_url TEXT,
                    screenshot_path TEXT,
                    snapshot_path TEXT,
                    result_payload TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_ms INTEGER
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_execution_results_article_id "
                "ON execution_results(article_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_execution_results_task_id "
                "ON execution_results(task_id)"
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    article_id TEXT PRIMARY KEY,
                    last_task_id TEXT,
                    publish_mode TEXT NOT NULL,
                    last_status TEXT NOT NULL,
                    draft_url TEXT,
                    article_url TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create_task(self, task: ArticleTask) -> None:
        now = utc_now_iso()
        payload = json.dumps(task.model_dump(mode="json"), ensure_ascii=False)

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO article_tasks (
                    task_id,
                    article_id,
                    title,
                    publish_mode,
                    source,
                    status,
                    priority,
                    scheduled_at,
                    task_payload,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.article_id,
                    task.title,
                    task.publish_mode.value,
                    task.source,
                    TaskStatus.PENDING.value,
                    task.priority,
                    task.scheduled_at,
                    payload,
                    now,
                    now,
                ),
            )

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE article_tasks
                SET status = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status.value, utc_now_iso(), task_id),
            )

    def insert_execution_result(self, result: ExecutionResult) -> None:
        payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO execution_results (
                    task_id,
                    article_id,
                    status,
                    final_stage,
                    retry_count,
                    error_type,
                    error_message,
                    manual_reason,
                    draft_url,
                    article_url,
                    screenshot_path,
                    snapshot_path,
                    result_payload,
                    started_at,
                    ended_at,
                    duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.task_id,
                    result.article_id,
                    result.status.value,
                    result.final_stage.value,
                    result.retry_count,
                    result.error_type.value if result.error_type else None,
                    result.error_message,
                    result.manual_reason,
                    result.draft_url,
                    result.article_url,
                    result.screenshot_path,
                    result.snapshot_path,
                    payload,
                    result.started_at,
                    result.ended_at,
                    result.duration_ms,
                ),
            )

    def get_latest_result(self, article_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM execution_results
                WHERE article_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id,),
            ).fetchone()

        return dict(row) if row else None

    def get_idempotency_record(self, article_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM idempotency_records
                WHERE article_id = ?
                """,
                (article_id,),
            ).fetchone()

        return dict(row) if row else None

    def upsert_idempotency_record(
        self,
        article_id: str,
        last_task_id: str,
        publish_mode: PublishMode,
        last_status: TaskStatus,
        draft_url: str | None = None,
        article_url: str | None = None,
    ) -> None:
        now = utc_now_iso()

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO idempotency_records (
                    article_id,
                    last_task_id,
                    publish_mode,
                    last_status,
                    draft_url,
                    article_url,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    last_task_id = excluded.last_task_id,
                    publish_mode = excluded.publish_mode,
                    last_status = excluded.last_status,
                    draft_url = excluded.draft_url,
                    article_url = excluded.article_url,
                    updated_at = excluded.updated_at
                """,
                (
                    article_id,
                    last_task_id,
                    publish_mode.value,
                    last_status.value,
                    draft_url,
                    article_url,
                    now,
                ),
            )
