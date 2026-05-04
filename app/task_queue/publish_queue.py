from __future__ import annotations

import json
from pathlib import Path

from app.schemas.article_task import ArticleTask
from app.schemas.enums import PublishMode
from app.store.task_store import TaskStore


def prepare_publish_task(*, source_task_path: Path, output_path: Path, store: TaskStore) -> Path:
    payload = json.loads(source_task_path.read_text(encoding="utf-8"))
    task = ArticleTask(**payload)
    existing = store.get_idempotency_record(task.article_id)
    draft_url = None if not existing else existing.get("draft_url")
    if not draft_url:
        raise ValueError(f"no saved draft url found for article_id={task.article_id}")

    task.publish_mode = PublishMode.PUBLISH
    metadata = dict(task.metadata)
    metadata["draft_url"] = draft_url
    metadata["review_status"] = "approved"
    metadata["ready_for_publish"] = True
    task.metadata = metadata

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path
