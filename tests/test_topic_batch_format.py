import json
from pathlib import Path

from typer.testing import CliRunner

from app.business.ops import validate_topic_batch_payload, write_topic_batch_files
from app.main import app

runner = CliRunner()


def _full_batch_payload() -> dict:
    topics = []
    for idx in range(1, 9):
        topics.append(
            {
                "number": idx,
                "title": f"选题 {idx}",
                "audience": "刚开始做 CSDN 的作者",
                "account": "技术小甜甜",
                "column": "专栏增长",
                "reason": f"理由 {idx}",
                "expected_value": f"价值 {idx}",
                "why_now": f"时机 {idx}",
                "cta": f"CTA {idx}",
                "role": "引流题" if idx <= 3 else ("信任题" if idx <= 6 else "转化题"),
                "risk": f"风险 {idx}",
                "priority": "主推" if idx <= 6 else "备用",
            }
        )
    return {
        "account": "技术小甜甜",
        "generated_at": "2026-04-20T09:00:00Z",
        "batch_strategy": "围绕新号未来 3 天的引流 + 信任 + 转化组合出题",
        "writing_order": ["选题 1", "选题 2", "选题 3"],
        "changes_from_previous": ["减少纯概念题", "增加实操避坑题"],
        "topics": topics,
    }


def test_validate_topic_batch_payload_requires_exactly_8_topics():
    payload = _full_batch_payload()
    payload["topics"] = payload["topics"][:7]

    try:
        validate_topic_batch_payload(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "exactly 8 topics" in str(exc)



def test_write_topic_batch_files_creates_json_and_markdown(tmp_path: Path):
    result = write_topic_batch_files(batch=_full_batch_payload(), date="2026-04-20", base_dir=tmp_path)

    assert result["json_path"].exists()
    assert result["md_path"].exists()
    md_content = result["md_path"].read_text(encoding="utf-8")
    assert "选题批次" in md_content
    assert "批次策略" in md_content
    assert "建议写作顺序" in md_content
    assert "题型角色" in md_content
    assert "风险/不确定点" in md_content



def test_save_topic_batch_cli_validates_and_persists(tmp_path: Path):
    input_path = tmp_path / "batch.json"
    input_path.write_text(json.dumps(_full_batch_payload(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "save-topic-batch",
            "--date",
            "2026-04-20",
            "--batch-json-path",
            str(input_path),
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Topic batch saved" in result.output
    saved_dir = tmp_path / "data" / "business" / "topic_batches"
    assert len(list(saved_dir.glob("*.json"))) == 1
    assert len(list(saved_dir.glob("*.md"))) == 1
