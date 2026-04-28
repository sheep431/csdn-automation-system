from pathlib import Path

from app.schemas.article_task import ArticleTask
from app.schemas.enums import PublishMode, TaskStatus
from app.store.task_store import TaskStore


def test_idempotency_record_upsert_and_read(tmp_path: Path):
    db_path = tmp_path / "test.db"
    store = TaskStore(db_path)
    store.init_db()

    store.upsert_idempotency_record(
        article_id="csdn-test-001",
        last_task_id="task_001",
        publish_mode=PublishMode.DRAFT,
        last_status=TaskStatus.SUCCESS,
        draft_url="https://draft.example.com/1",
    )

    record = store.get_idempotency_record("csdn-test-001")
    assert record is not None
    assert record["article_id"] == "csdn-test-001"
    assert record["last_task_id"] == "task_001"
    assert record["publish_mode"] == "draft"
    assert record["last_status"] == "success"
    assert record["draft_url"] == "https://draft.example.com/1"


def test_create_task_and_latest_result_roundtrip(tmp_path: Path):
    db_path = tmp_path / "test.db"
    store = TaskStore(db_path)
    store.init_db()

    task = ArticleTask(
        task_id="task_001",
        article_id="csdn-test-002",
        title="测试标题",
        body_markdown="# 正文",
        tags=["Python"],
        publish_mode=PublishMode.DRAFT,
    )

    store.create_task(task)
    record = store.get_idempotency_record("csdn-test-002")
    assert record is None
