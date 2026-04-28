import json
from pathlib import Path

from typer.testing import CliRunner

from app.business.ops import process_topic_batch_feedback
from app.main import app

runner = CliRunner()


def _sample_batch(tmp_path: Path) -> Path:
    batch_dir = tmp_path / "data" / "business" / "topic_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_path = batch_dir / "topic-batch_2026-04-19_090000.json"
    payload = {
        "account": "技术小甜甜",
        "generated_at": "2026-04-19T09:00:00Z",
        "topics": [
            {
                "number": 1,
                "title": "CSDN 新手起号最小闭环",
                "audience": "刚开始做 CSDN 的新手",
                "reason": "适合作为引流题",
                "cta": "导向起号专栏",
                "priority": "主推",
            },
            {
                "number": 2,
                "title": "CSDN 内容战略的底层逻辑",
                "audience": "想系统理解平台的作者",
                "reason": "偏概念解释",
                "cta": "导向策略专栏",
                "priority": "主推",
            },
            {
                "number": 3,
                "title": "CSDN 发文最容易踩的 5 个坑",
                "audience": "准备发文的人",
                "reason": "适合做实操避坑题",
                "cta": "导向发文 SOP 专栏",
                "priority": "备用",
            },
        ],
    }
    batch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return batch_path


def test_process_topic_batch_feedback_writes_feedback_and_learning_files(tmp_path: Path):
    batch_path = _sample_batch(tmp_path)

    result = process_topic_batch_feedback(
        date="2026-04-19",
        batch_path=batch_path,
        feedback="第 2 个不要，太泛了。第 3 个角度留着，但改成更实操的避坑文。以后少来纯概念题，这种能带专栏点击的题以后多来一点。",
        base_dir=tmp_path,
        account="技术小甜甜",
    )

    for path in result.values():
        assert path.exists()

    revised_payload = json.loads(result["revised_json_path"].read_text(encoding="utf-8"))
    titles = [item["title"] for item in revised_payload["topics"]]
    assert "CSDN 内容战略的底层逻辑" not in titles
    assert any(item["title"] == "CSDN 发文最容易踩的 5 个坑" and item.get("revision_note") for item in revised_payload["topics"])
    assert any(item["status"] == "rejected" for item in revised_payload["usage_sync"])
    assert any(item["status"] == "approved" for item in revised_payload["usage_sync"])

    feedback_payload = json.loads(result["feedback_json_path"].read_text(encoding="utf-8"))
    assert len(feedback_payload["topic_actions"]) == 2
    assert any(rule["pattern"] == "纯概念题" for rule in feedback_payload["normalized_rules"])
    assert any(rule["pattern"] == "高转化题" for rule in feedback_payload["normalized_rules"])
    assert any(item["status"] == "rejected" for item in feedback_payload["usage_sync"])

    learning_payload = json.loads(result["rules_json_path"].read_text(encoding="utf-8"))
    assert any(rule["pattern"] == "实操避坑题" for rule in learning_payload["rules"])


def test_apply_topic_feedback_cli_creates_revised_batch(tmp_path: Path):
    batch_path = _sample_batch(tmp_path)

    result = runner.invoke(
        app,
        [
            "apply-topic-feedback",
            "--date",
            "2026-04-19",
            "--batch-path",
            str(batch_path),
            "--feedback",
            "第 2 个不要，太泛了。以后少来纯概念题。",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Topic feedback applied" in result.output
    revised_dir = tmp_path / "data" / "business" / "topic_batches"
    revised_files = list(revised_dir.glob("*.revised.json"))
    assert len(revised_files) == 1
    revised_payload = json.loads(revised_files[0].read_text(encoding="utf-8"))
    assert len(revised_payload["topics"]) == 2
