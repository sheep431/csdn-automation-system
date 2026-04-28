from app.schemas.article_task import ArticleTask
from app.schemas.enums import PublishMode


def test_article_task_accepts_valid_input():
    task = ArticleTask(
        article_id="csdn-test-001",
        title="测试标题",
        body_markdown="# 正文\n\n内容",
        tags=["Python", "自动化"],
        publish_mode=PublishMode.DRAFT,
    )

    assert task.article_id == "csdn-test-001"
    assert task.title == "测试标题"
    assert task.publish_mode == PublishMode.DRAFT
    assert task.tags == ["Python", "自动化"]


def test_article_task_rejects_empty_title():
    try:
        ArticleTask(
            article_id="csdn-test-001",
            title="   ",
            body_markdown="# 正文",
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "title cannot be empty" in str(exc)


def test_article_task_normalizes_duplicate_tags():
    task = ArticleTask(
        article_id="csdn-test-001",
        title="测试标题",
        body_markdown="# 正文",
        tags=["Python", "Python", " 自动化 ", ""],
    )

    assert task.tags == ["Python", "自动化"]


def test_publishable_requires_tags_when_publish_mode_enabled():
    task = ArticleTask(
        article_id="csdn-test-001",
        title="测试标题",
        body_markdown="# 正文",
        tags=[],
        publish_mode=PublishMode.PUBLISH,
    )

    try:
        task.validate_publishable(allow_publish=True)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "requires at least one tag" in str(exc)
