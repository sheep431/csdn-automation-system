import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.schemas.enums import PublishMode
from app.task_queue.markdown_queue import enqueue_markdown_drafts

runner = CliRunner()


def test_enqueue_markdown_draft_creates_pending_task_with_review_metadata(tmp_path: Path):
    draft = tmp_path / "20260309_paid_dify.md"
    draft.write_text(
        "# Dify 生产落地的 7 个关键设计\n\n正文第一段\n\n- 要点1\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "pending"

    created = enqueue_markdown_drafts(
        input_path=draft,
        output_dir=output_dir,
        profile="new-main",
        source="generated",
    )

    assert len(created) == 1
    payload = json.loads(created[0].read_text(encoding="utf-8"))
    assert payload["title"] == "Dify 生产落地的 7 个关键设计"
    assert payload["body_markdown"].startswith("# Dify 生产落地的 7 个关键设计")
    assert payload["publish_mode"] == PublishMode.DRAFT.value
    assert payload["source"] == "generated"
    assert payload["metadata"]["account_profile"] == "new-main"
    assert payload["metadata"]["review_status"] == "pending"
    assert payload["metadata"]["requires_human_review"] is True
    assert payload["metadata"]["origin_markdown_path"] == str(draft)



def test_enqueue_markdown_dir_processes_multiple_markdown_files_and_ignores_non_markdown(tmp_path: Path):
    draft_dir = tmp_path / "drafts"
    draft_dir.mkdir()
    (draft_dir / "a.md").write_text("# 标题A\n\nA正文", encoding="utf-8")
    (draft_dir / "b.markdown").write_text("# 标题B\n\nB正文", encoding="utf-8")
    (draft_dir / "note.txt").write_text("ignore me", encoding="utf-8")

    created = enqueue_markdown_drafts(
        input_path=draft_dir,
        output_dir=tmp_path / "pending",
        profile="old-traffic",
    )

    assert len(created) == 2
    created_names = sorted(path.name for path in created)
    assert created_names[0].endswith("a.json")
    assert created_names[1].endswith("b.json")



def test_enqueue_markdown_cli_creates_task_files(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text("# CLI 标题\n\nCLI 正文", encoding="utf-8")
    output_dir = tmp_path / "pending"

    result = runner.invoke(
        app,
        [
            "enqueue-markdown",
            "--input-path",
            str(draft),
            "--output-dir",
            str(output_dir),
            "--profile",
            "new-main",
        ],
    )

    assert result.exit_code == 0
    created = sorted(output_dir.glob("*.json"))
    assert len(created) == 1
    payload = json.loads(created[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["account_profile"] == "new-main"
