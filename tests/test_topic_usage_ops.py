import json
from pathlib import Path

from typer.testing import CliRunner

from app.business.ops import build_baseline_topic_libraries_from_full_capture, is_topic_used, mark_topic_used, mark_topic_published_from_execution, topic_usage_report
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


def _build_library_for_batch(tmp_path: Path) -> Path:
    capture = tmp_path / "full.json"
    capture.write_text(
        json.dumps(
            {
                "columns": [
                    {
                        "title": "专栏增长",
                        "description": "测试专栏",
                        "articles": [{"title": "旧文 1"}],
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    result = build_baseline_topic_libraries_from_full_capture(
        date="2026-04-20",
        account="技术小甜甜",
        capture_path=capture,
        base_dir=tmp_path,
    )
    library_path = Path(result["libraries"][0]["json_path"])
    payload = json.loads(library_path.read_text(encoding="utf-8"))
    payload["modules"] = [
        {
            "module": "growth-module",
            "name": "增长模块",
            "goal": "测试",
            "role": "引流题",
            "status": "partial",
            "keywords": ["增长"],
            "candidate_topics": [
                {"candidate_id": "test-account::专栏增长::growth-module::01", "title": "选题 A", "status": "unused", "source": "baseline_library", "role": "引流题", "module": "growth-module"},
                {"candidate_id": "test-account::专栏增长::growth-module::02", "title": "选题 B", "status": "unused", "source": "baseline_library", "role": "引流题", "module": "growth-module"},
            ],
        }
    ]
    library_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return library_path


def test_mark_topic_used_records_ledger_and_is_detectable(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)
    _build_library_for_batch(tmp_path)

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
    library_payload = json.loads(result["topic_library_json_path"].read_text(encoding="utf-8"))
    candidate = library_payload["modules"][0]["candidate_topics"][1]
    assert candidate["title"] == "选题 B"
    assert candidate["status"] == "used"



def test_mark_topic_published_from_execution_updates_existing_entry_and_library(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)
    library_path = _build_library_for_batch(tmp_path)

    mark_topic_used(
        date="2026-04-20",
        batch_path=batch_path,
        topic_number=2,
        status="used",
        base_dir=tmp_path,
        notes="已进入草稿阶段",
    )

    result = mark_topic_published_from_execution(
        date="2026-04-21",
        account="技术小甜甜",
        title="选题 B",
        column="专栏增长",
        base_dir=tmp_path,
        notes="正式发布成功: https://example.com/article/2",
    )

    ledger = json.loads(result["ledger_path"].read_text(encoding="utf-8"))
    entry = next(item for item in ledger["entries"] if item["title"] == "选题 B")
    assert entry["status"] == "published"
    assert entry["last_topic_number"] == 2
    assert entry["notes"] == "正式发布成功: https://example.com/article/2"
    assert any(h["status"] == "published" for h in entry["history"])

    library_payload = json.loads(library_path.read_text(encoding="utf-8"))
    candidate = library_payload["modules"][0]["candidate_topics"][1]
    assert candidate["title"] == "选题 B"
    assert candidate["status"] == "published"
    assert candidate["notes"] == "正式发布成功: https://example.com/article/2"


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
