from __future__ import annotations

from app.schemas.article_task import ArticleTask


def is_task_ready_for_execution(task: ArticleTask, approved_only: bool = False) -> bool:
    if not approved_only:
        return True

    requires_review = bool(task.metadata.get("requires_human_review", False))
    if not requires_review:
        return True

    review_status = str(task.metadata.get("review_status", "pending")).strip().lower()
    return review_status == "approved"
