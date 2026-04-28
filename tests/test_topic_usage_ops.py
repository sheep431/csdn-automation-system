import json
from pathlib import Path

from typer.testing import CliRunner

from app.business.ops import is_topic_used, mark_topic_used, topic_usage_report
from app.main import app

runner = CliRunner()


def _batch_with_topics(tmp_path: Path) -> Path:
    batch_dir = tmp_path / "data" / "business" / "topic_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_path = batch_dir / "topic-batch_20260420090000.json"
    payload = {
        "account": "技术小甜甜",
        "generated_at": "2026-04-20T09:00:00Z",
        "batch_strategy": "围绕新号 3 天内容节奏生成",
        "writing_order": ["选题 A", "选题 B", "选题 C"],
        "topics": [
            {
                "number": i,
                "title": title,
                "audience": "CSDN 新手作者",
                "account": "技术小甜甜",
                "column": "专栏增长",
                "reason": f"理由 {i}",
                "expected_value": f"价值 {i}",
                "why_now": f"现在写 {i}",
                "cta": f"CTA {i}",
                "role": "引流题" if i <= 3 else ("信任题" if i <= 6 else "转化题"),
                "risk": f"风险 {i}",
                "priority": "主推" if i <= 6 else "备用",
            }
            for i, title in enumerate([
                "选题 A",
                "选题 B",
                "选题 C",
                "选题 D",
                "选题 E",
                "选题 F",
                "选题 G",
                "选题 H",
            ], start=1)
        ],
    }
    batch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return batch_path


def test_mark_topic_used_records_ledger_and_is_detectable(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)

    result = mark_topic_used(
        date="2026-04-20",
        batch_path=batch_path,
        topic_number=2,
        status="used",
        base_dir=tmp_path,
        notes="进入实际写作队列",
    )

    for path in result.values():
        assert path.exists()

    ledger = json.loads(result["ledger_path"].read_text(encoding="utf-8"))
    assert len(ledger["entries"]) == 1
    entry = ledger["entries"][0]
    assert entry["title"] == "选题 B"
    assert entry["status"] == "used"
    assert is_topic_used(title="选题 B", base_dir=tmp_path, account="技术小甜甜") is True
    assert is_topic_used(title="选题 X", base_dir=tmp_path, account="技术小甜甜") is False



def test_topic_usage_report_summarizes_usage(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)
    mark_topic_used(
        date="2026-04-20",
        batch_path=batch_path,
        topic_number=1,
        status="approved",
        base_dir=tmp_path,
    )
    mark_topic_used(
        date="2026-04-20",
        batch_path=batch_path,
        topic_number=2,
        status="published",
        base_dir=tmp_path,
    )

    report_path = topic_usage_report(date="2026-04-20", base_dir=tmp_path, account="技术小甜甜")
    content = report_path.read_text(encoding="utf-8")
    assert "选题使用报告" in content
    assert "approved: 1" in content
    assert "published: 1" in content
    assert "选题 A" in content
    assert "选题 B" in content



def test_mark_topic_used_and_topic_usage_report_cli(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)

    mark_result = runner.invoke(
        app,
        [
            "mark-topic-used",
            "--date",
            "2026-04-20",
            "--batch-path",
            str(batch_path),
            "--topic-number",
            "3",
            "--status",
            "used",
            "--notes",
            "避免后续重复出题",
            "--base-dir",
            str(tmp_path),
        ],
    )
    assert mark_result.exit_code == 0
    assert "Topic usage recorded" in mark_result.output

    report_result = runner.invoke(
        app,
        [
            "topic-usage-report",
            "--date",
            "2026-04-20",
            "--account",
            "技术小甜甜",
            "--base-dir",
            str(tmp_path),
        ],
    )
    assert report_result.exit_code == 0
    assert "Topic usage report saved" in report_result.output
