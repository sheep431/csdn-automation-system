import json
from pathlib import Path

from app.schemas.article_task import ArticleTask
from app.schemas.enums import PublishMode, TaskStatus
from app.store.task_store import TaskStore
from app.task_queue.publish_queue import prepare_publish_task


def test_prepare_publish_task_promotes_draft_and_attaches_latest_draft_url(tmp_path: Path):
    db_path = tmp_path / "tasks.db"
    store = TaskStore(db_path)
    store.init_db()

    draft_task = ArticleTask(
        article_id="new-main-2026-05-03-traffic-1",
        title="[AI] 大家都在聊工作流自动化，真正值得普通团队先学的到底是哪一步？",
        body_markdown="# 标题\n\n正文",
        tags=["人工智能", "自动化", "工作流"],
        category="技术前沿每日速读",
        publish_mode=PublishMode.DRAFT,
        metadata={
            "account_profile": "new-main",
            "review_status": "approved",
            "requires_human_review": True,
            "column": "技术前沿每日速读",
            "cover_image_path": "/tmp/trend-cover.jpg",
        },
    )
    source_task_path = tmp_path / "draft-task.json"
    source_task_path.write_text(json.dumps(draft_task.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")

    store.upsert_idempotency_record(
        article_id=draft_task.article_id,
        last_task_id="task_old",
        publish_mode=PublishMode.DRAFT,
        last_status=TaskStatus.SUCCESS,
        draft_url="https://editor.csdn.net/md?articleId=160742999",
        article_url=None,
    )

    output_path = tmp_path / "publish-task.json"
    result_path = prepare_publish_task(
        source_task_path=source_task_path,
        output_path=output_path,
        store=store,
    )

    assert result_path == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["publish_mode"] == PublishMode.PUBLISH.value
    assert payload["article_id"] == draft_task.article_id
    assert payload["title"] == draft_task.title
    assert payload["tags"] == ["人工智能", "自动化", "工作流"]
    assert payload["category"] == "技术前沿每日速读"
    assert payload["metadata"]["draft_url"] == "https://editor.csdn.net/md?articleId=160742999"
    assert payload["metadata"]["review_status"] == "approved"
    assert payload["metadata"]["ready_for_publish"] is True
