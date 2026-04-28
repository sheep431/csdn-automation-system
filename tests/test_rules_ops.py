from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.rules.ops import check_draft_readiness, check_publish_readiness, score_topic

runner = CliRunner()


def test_score_topic_classifies_a_bucket_for_high_value_high_relevance_easy_write():
    result = score_topic(value_score=5, relevance_score=4, cost_score=5)

    assert result["total"] == 14
    assert result["bucket"] == "A"
    assert result["recommended"] is True


def test_check_draft_readiness_rejects_placeholder_content():
    result = check_draft_readiness(
        title="  ",
        body_markdown="# 标题\n\nTODO 待补充正文",
    )

    assert result["ready"] is False
    assert "标题清楚" in result["reasons"]
    assert "没有大量占位符" in result["reasons"]


def test_check_publish_readiness_requires_approved_review_and_open_link():
    result = check_publish_readiness(
        draft_exists=True,
        review_status="needs_revision",
        draft_url="https://editor.csdn.net/md/?articleId=123",
        owner="技术小甜甜",
    )

    assert result["publishable"] is False
    assert "审核已通过" in result["reasons"]


def test_score_topic_cli_writes_rule_record(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "score-topic",
            "--date",
            "2026-04-19",
            "--title",
            "Python 字典去重",
            "--account",
            "技术小甜甜",
            "--value-score",
            "5",
            "--relevance-score",
            "4",
            "--cost-score",
            "5",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    output_dir = tmp_path / "data" / "rules" / "assessments"
    files = list(output_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Python 字典去重" in content
    assert "A 池" in content
    assert "recommended" not in content
