from app.schemas.article_task import ArticleTask
from app.task_queue.review_gate import is_task_ready_for_execution


def test_review_gate_blocks_pending_human_review():
    task = ArticleTask(
        article_id="draft-001",
        title="待审文章",
        body_markdown="# 正文",
        metadata={
            "requires_human_review": True,
            "review_status": "pending",
        },
    )

    assert is_task_ready_for_execution(task, approved_only=True) is False



def test_review_gate_allows_approved_human_review():
    task = ArticleTask(
        article_id="draft-002",
        title="已审文章",
        body_markdown="# 正文",
        metadata={
            "requires_human_review": True,
            "review_status": "approved",
        },
    )

    assert is_task_ready_for_execution(task, approved_only=True) is True



def test_review_gate_allows_non_review_tasks():
    task = ArticleTask(
        article_id="draft-003",
        title="无需审核",
        body_markdown="# 正文",
        metadata={
            "requires_human_review": False,
        },
    )

    assert is_task_ready_for_execution(task, approved_only=True) is True
