import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.schemas.enums import PublishMode
from app.task_queue import markdown_queue
from app.task_queue.markdown_queue import _normalize_markdown_for_csdn, enqueue_markdown_drafts

runner = CliRunner()


def test_normalize_markdown_for_csdn_adds_blank_lines_for_lists_and_headings():
    raw = "# 标题\n说明文字：\n- 要点1\n- 要点2\n## 小节\n继续正文\n1. 步骤一\n2. 步骤二\n"
    normalized = _normalize_markdown_for_csdn(raw)
    assert "说明文字：\n\n- 要点1" in normalized
    assert "- 要点2\n\n## 小节" in normalized
    assert "继续正文\n\n1. 步骤一" in normalized



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



def test_enqueue_markdown_draft_can_be_preapproved_for_auto_run(tmp_path: Path):
    draft = tmp_path / "approved.md"
    draft.write_text("# 已批准标题\n\n可直接上传到草稿站的正文", encoding="utf-8")

    created = enqueue_markdown_drafts(
        input_path=draft,
        output_dir=tmp_path / "pending",
        profile="new-main",
        review_status="approved",
    )

    payload = json.loads(created[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["review_status"] == "approved"
    assert payload["metadata"]["requires_human_review"] is True


def test_enqueue_markdown_enriches_column_tags_and_header_image(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "trend-cover.jpg"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setattr(
        markdown_queue,
        "COLUMN_IMAGE_REGISTRY",
        {
            "技术前沿每日速读": {
                "header_image_path": str(image_path),
                "header_image_alt": "技术前沿每日速读头图",
                "cover_image_path": str(image_path),
                "default_tags": ["人工智能", "自动化", "技术趋势"],
            }
        },
        raising=False,
    )

    draft = tmp_path / "traffic.md"
    draft.write_text(
        "# [AI] 大家都在聊工作流自动化，真正值得普通团队先学的到底是哪一步？\n\n"
        "> 账号定位：技术小甜甜（new-main）\n"
        "> 今日目标：traffic\n"
        "> 专栏/系列：技术前沿每日速读\n\n"
        "正文第一段\n",
        encoding="utf-8",
    )

    created = enqueue_markdown_drafts(
        input_path=draft,
        output_dir=tmp_path / "pending",
        profile="new-main",
        review_status="approved",
    )

    payload = json.loads(created[0].read_text(encoding="utf-8"))
    assert payload["category"] == "技术前沿每日速读"
    assert payload["tags"] == ["人工智能", "自动化", "工作流"]
    assert payload["metadata"]["column"] == "技术前沿每日速读"
    assert payload["metadata"]["cover_image_path"] == str(image_path)
    assert payload["metadata"]["header_image_path"] == str(image_path)
    assert payload["metadata"]["header_image_alt"] == "技术前沿每日速读头图"
    assert "![技术前沿每日速读头图](" not in payload["body_markdown"]



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
            "--review-status",
            "approved",
        ],
    )

    assert result.exit_code == 0
    created = sorted(output_dir.glob("*.json"))
    assert len(created) == 1
    payload = json.loads(created[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["account_profile"] == "new-main"
    assert payload["metadata"]["review_status"] == "approved"
