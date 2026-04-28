from pathlib import Path
import json

from typer.testing import CliRunner

from app.main import app
from app.state.ops import (
    build_daily_column_allocations_from_slots,
    read_state_record,
    set_column_lifecycle,
    snapshot_state,
    upsert_state_record,
    write_column_portfolio_review,
    write_daily_column_allocation,
)

runner = CliRunner()


def test_upsert_state_record_writes_latest_and_history(tmp_path: Path):
    path1 = upsert_state_record(
        object_type="topic",
        object_id="topic-001",
        state="candidate",
        notes="来自第 0 层周报",
        base_dir=tmp_path,
        attributes={"account": "技术小甜甜", "title": "Python 字典去重"},
    )
    path2 = upsert_state_record(
        object_type="topic",
        object_id="topic-001",
        state="scored",
        notes="已进入 A 池",
        base_dir=tmp_path,
        attributes={"account": "技术小甜甜", "title": "Python 字典去重", "bucket": "A"},
    )

    assert path1 == path2
    assert path2.exists()
    content = path2.read_text(encoding="utf-8")
    assert "scored" in content
    assert "A" in content
    assert "history_count" in content

    history_file = tmp_path / "data" / "state" / "history" / "topic" / "topic-001.jsonl"
    assert history_file.exists()
    history_lines = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(history_lines) == 2
    assert '"state": "candidate"' in history_lines[0]
    assert '"state": "scored"' in history_lines[1]


def test_set_column_lifecycle_writes_column_state_record(tmp_path: Path):
    path = set_column_lifecycle(
        date="2026-04-25",
        account="技术小甜甜",
        column="AI实践-Dify专栏",
        lifecycle_state="active_revenue",
        role="flagship_revenue",
        notes="当前旗舰收益专栏",
        base_dir=tmp_path,
    )

    assert path.exists()
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["object_type"] == "column"
    assert record["state"] == "active_revenue"
    assert record["attributes"]["column"] == "AI实践-Dify专栏"
    assert record["attributes"]["role"] == "flagship_revenue"


def test_write_daily_column_allocation_creates_artifacts_and_state(tmp_path: Path):
    set_column_lifecycle(
        date="2026-04-25",
        account="技术小甜甜",
        column="AI实践-Dify专栏",
        lifecycle_state="active_revenue",
        role="flagship_revenue",
        notes="旗舰收益专栏",
        base_dir=tmp_path,
    )
    set_column_lifecycle(
        date="2026-04-25",
        account="技术小甜甜",
        column="技术前沿每日速读",
        lifecycle_state="active_traffic",
        role="traffic_support",
        notes="引流专栏",
        base_dir=tmp_path,
    )

    result = write_daily_column_allocation(
        date="2026-04-25",
        account="技术小甜甜",
        allocations=[
            {
                "slot_index": 1,
                "column": "AI实践-Dify专栏",
                "role": "flagship_revenue",
                "lifecycle_state": "active_revenue",
                "score": 9.5,
                "rationale": "旗舰主线继续承接 Dify 收益位",
                "source_signals": ["live batch", "column asset"],
            },
            {
                "slot_index": 2,
                "column": "技术前沿每日速读",
                "role": "traffic_support",
                "lifecycle_state": "active_traffic",
                "score": 7.0,
                "rationale": "免费专栏承担引流位，维持活性",
                "source_signals": ["traffic column", "recent gap"],
            },
        ],
        notes="当天两篇分散到收益专栏与免费引流专栏",
        source_signals=["strategy output", "sales signal"],
        base_dir=tmp_path,
    )

    assert result["json_path"].exists()
    assert result["md_path"].exists()
    assert result["state_path"].exists()

    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["allocation_count"] == 2
    assert payload["allocations"][1]["lifecycle_state"] == "active_traffic"
    md = result["md_path"].read_text(encoding="utf-8")
    assert "当日专栏分配" in md
    assert "技术前沿每日速读" in md

    state = read_state_record(
        object_type="column_allocation",
        object_id="2026-04-25__技术小甜甜",
        base_dir=tmp_path,
    )
    assert state is not None
    assert state["state"] == "planned"
    assert "技术前沿每日速读" in state["attributes"]["columns"]


def test_build_daily_column_allocations_from_slots_uses_lifecycle_when_available(tmp_path: Path):
    set_column_lifecycle(
        date="2026-04-25",
        account="技术小甜甜",
        column="技术前沿每日速读",
        lifecycle_state="active_traffic",
        role="traffic_support",
        notes="引流专栏",
        base_dir=tmp_path,
    )

    result = build_daily_column_allocations_from_slots(
        date="2026-04-25",
        account="技术小甜甜",
        slots=[
            {
                "slot_index": 1,
                "column": "AI实践-Dify专栏",
                "why_now": "旗舰主更",
            },
            {
                "slot_index": 2,
                "column": "技术前沿每日速读",
                "notes": "承接免费引流位",
            },
        ],
        notes="自动生成",
        source_signals=["publish-day manifest"],
        base_dir=tmp_path,
    )

    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["allocations"][0]["role"] == "flagship_revenue"
    assert payload["allocations"][1]["role"] == "traffic_support"
    assert payload["allocations"][1]["lifecycle_state"] == "active_traffic"


def test_write_column_portfolio_review_summarizes_lifecycle_allocations_and_signals(tmp_path: Path):
    set_column_lifecycle(
        date="2026-04-25",
        account="技术小甜甜",
        column="AI实践-Dify专栏",
        lifecycle_state="active_revenue",
        role="flagship_revenue",
        notes="旗舰收益专栏",
        base_dir=tmp_path,
    )
    set_column_lifecycle(
        date="2026-04-25",
        account="技术小甜甜",
        column="技术前沿每日速读",
        lifecycle_state="active_traffic",
        role="traffic_support",
        notes="免费引流专栏",
        base_dir=tmp_path,
    )
    write_daily_column_allocation(
        date="2026-04-25",
        account="技术小甜甜",
        allocations=[
            {
                "slot_index": 1,
                "column": "AI实践-Dify专栏",
                "role": "flagship_revenue",
                "lifecycle_state": "active_revenue",
                "score": 9.5,
                "rationale": "收益主位",
                "source_signals": ["strategy output"],
            },
            {
                "slot_index": 2,
                "column": "技术前沿每日速读",
                "role": "traffic_support",
                "lifecycle_state": "active_traffic",
                "score": 7.1,
                "rationale": "免费引流位",
                "source_signals": ["traffic signal"],
            },
        ],
        base_dir=tmp_path,
    )
    strategy_dir = tmp_path / "data" / "business" / "strategy_outputs"
    sales_dir = tmp_path / "data" / "intel" / "sales"
    strategy_dir.mkdir(parents=True, exist_ok=True)
    sales_dir.mkdir(parents=True, exist_ok=True)
    (strategy_dir / "2026-04-25_技术小甜甜_strategy.md").write_text("# 策略\n\n- AI实践-Dify专栏 继续做收益主位\n", encoding="utf-8")
    (sales_dir / "2026-04-25.md").write_text("# 专栏与转化记录\n\n- 专栏: 技术前沿每日速读\n- 指标: click\n- 数值: 8\n", encoding="utf-8")

    result = write_column_portfolio_review(date="2026-04-25", account="技术小甜甜", base_dir=tmp_path)

    assert result["json_path"].exists()
    assert result["md_path"].exists()
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["column_count"] == 2
    assert payload["lifecycle_counts"]["active_revenue"] == 1
    assert payload["lifecycle_counts"]["active_traffic"] == 1
    assert any(item["column"] == "技术前沿每日速读" for item in payload["columns"])
    md = result["md_path"].read_text(encoding="utf-8")
    assert "专栏组合经营复盘" in md
    assert "建议动作" in md
    assert "技术前沿每日速读" in md



def test_snapshot_state_summarizes_current_records(tmp_path: Path):
    upsert_state_record(
        object_type="topic",
        object_id="topic-001",
        state="scored",
        notes="A 池",
        base_dir=tmp_path,
        attributes={"account": "技术小甜甜"},
    )
    upsert_state_record(
        object_type="draft",
        object_id="draft-001",
        state="waiting_review",
        notes="等待人工审核",
        base_dir=tmp_path,
        attributes={"account": "技术小甜甜", "topic_id": "topic-001"},
    )
    set_column_lifecycle(
        date="2026-04-25",
        account="技术小甜甜",
        column="企业级AI落地实战：从模型部署到应用系统",
        lifecycle_state="incubating",
        notes="作为第二收益点继续观察",
        base_dir=tmp_path,
    )

    path = snapshot_state(date="2026-04-19", base_dir=tmp_path, account="技术小甜甜")

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "状态快照" in content
    assert "topic" in content
    assert "draft" in content
    assert "column" in content
    assert "incubating" in content

    json_path = tmp_path / "data" / "state" / "snapshots" / "2026-04-19.json"
    assert json_path.exists()
    payload = json_path.read_text(encoding="utf-8")
    assert '"column"' in payload
    assert '"incubating"' in payload


def test_state_snapshot_cli_creates_summary_files(tmp_path: Path):
    upsert_state_record(
        object_type="publish_task",
        object_id="publish-001",
        state="pending",
        notes="等待发布",
        base_dir=tmp_path,
        attributes={"account": "技术小甜甜"},
    )

    result = runner.invoke(
        app,
        [
            "state-snapshot",
            "--date",
            "2026-04-19",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    md_path = tmp_path / "data" / "state" / "snapshots" / "2026-04-19.md"
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "publish_task" in content
    assert "pending" in content


def test_column_lifecycle_and_allocation_cli_commands(tmp_path: Path):
    lifecycle = runner.invoke(
        app,
        [
            "set-column-lifecycle",
            "--date", "2026-04-25",
            "--account", "技术小甜甜",
            "--column", "技术前沿每日速读",
            "--lifecycle-state", "active_traffic",
            "--role", "traffic_support",
            "--base-dir", str(tmp_path),
        ],
    )
    assert lifecycle.exit_code == 0
    assert "Column lifecycle saved" in lifecycle.output

    allocation = runner.invoke(
        app,
        [
            "write-daily-column-allocation",
            "--date", "2026-04-25",
            "--account", "技术小甜甜",
            "--slot", "1|AI实践-Dify专栏|flagship_revenue|active_revenue|旗舰收益位|9.8|live batch;strategy",
            "--slot", "2|技术前沿每日速读|traffic_support|active_traffic|免费引流位|7.1|traffic signal;feedback",
            "--source-signal", "strategy output",
            "--base-dir", str(tmp_path),
        ],
    )
    assert allocation.exit_code == 0
    assert "Daily column allocation saved" in allocation.output
    allocation_json = tmp_path / "data" / "business" / "column_allocations" / "daily-column-allocation_2026-04-25_技术小甜甜.json"
    assert allocation_json.exists()

    portfolio = runner.invoke(
        app,
        [
            "column-portfolio-review",
            "--date", "2026-04-25",
            "--account", "技术小甜甜",
            "--base-dir", str(tmp_path),
        ],
    )
    assert portfolio.exit_code == 0
    assert "Column portfolio review saved" in portfolio.output
    portfolio_json = tmp_path / "data" / "business" / "column_portfolio" / "column-portfolio-review_2026-04-25_技术小甜甜.json"
    assert portfolio_json.exists()
