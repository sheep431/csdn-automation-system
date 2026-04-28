from pathlib import Path

from typer.testing import CliRunner

from app.main import app

runner = CliRunner()


def test_collect_intel_cli_writes_account_snapshot(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "collect-intel",
            "--kind",
            "accounts",
            "--date",
            "2026-04-19",
            "--account",
            "new-main",
            "--summary",
            "阅读 120，收藏 18，专栏点击 7",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    output_file = tmp_path / "data" / "intel" / "accounts" / "2026-04-19.md"
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "new-main" in content
    assert "阅读 120" in content
    assert "专栏点击 7" in content



def test_log_feedback_cli_writes_feedback_record(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "log-feedback",
            "--date",
            "2026-04-19",
            "--account",
            "技术小甜甜",
            "--source",
            "review",
            "--feedback-type",
            "needs_revision",
            "--content",
            "标题需要更聚焦，正文可以更具体",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    output_file = tmp_path / "data" / "intel" / "feedback" / "2026-04-19.md"
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "needs_revision" in content
    assert "标题需要更聚焦" in content
    assert "技术小甜甜" in content



def test_review_intel_cli_builds_summary_from_collected_inputs(tmp_path: Path):
    accounts_dir = tmp_path / "data" / "intel" / "accounts"
    feedback_dir = tmp_path / "data" / "intel" / "feedback"
    accounts_dir.mkdir(parents=True)
    feedback_dir.mkdir(parents=True)
    (accounts_dir / "2026-04-19.md").write_text("# 账号快照\n\n阅读 100\n", encoding="utf-8")
    (feedback_dir / "2026-04-19.md").write_text("# 反馈\n\n用户想看选题方法\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "review-intel",
            "--period",
            "week",
            "--date",
            "2026-04-19",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    summary_file = tmp_path / "data" / "intel" / "insights" / "2026-04-19-week.md"
    assert summary_file.exists()
    content = summary_file.read_text(encoding="utf-8")
    assert "本周经营输入复盘" in content
    assert "## 数据概览" in content
    assert "## 用户反馈" in content
    assert "## 经营判断" in content
