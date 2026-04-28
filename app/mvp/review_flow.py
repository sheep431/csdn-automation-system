from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.schemas.article_task import ArticleTask
from app.schemas.execution_result import ExecutionResult
from app.schemas.enums import PublishMode


def build_new_main_sample_task() -> ArticleTask:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ArticleTask(
        article_id=f"new-main-sample-{timestamp}",
        title="CSDN 新号样例草稿：自动登录后的最小审稿流程",
        body_markdown=(
            "# CSDN 新号样例草稿：自动登录后的最小审稿流程\n\n"
            "这是一篇用于验证新号 MVP 流程的样例草稿。\n\n"
            "目标：自动登录 -> 保存草稿 -> 发给你审核 -> 你手动发布。\n"
        ),
        publish_mode=PublishMode.DRAFT,
        source="mvp_sample",
        metadata={
            "account_profile": "new-main",
            "requires_human_review": True,
            "review_status": "pending",
            "mvp_flow": True,
        },
    )


def persist_review_package(task: ArticleTask, result: ExecutionResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "article_id": task.article_id,
        "title": task.title,
        "account_profile": task.metadata.get("account_profile", "new-main"),
        "draft_url": result.draft_url,
        "review_message": (
            f"请审核这篇新号样例草稿：{task.title}\n"
            f"草稿链接：{result.draft_url or '（尚未生成）'}\n"
            "如果同意，请直接打开链接手动发布；如果不同意，请把修改点发给我，我会继续学习调整。"
        ),
    }
    path = output_dir / f"{task.article_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
