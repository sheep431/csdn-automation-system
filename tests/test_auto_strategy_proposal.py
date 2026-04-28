from pathlib import Path
import json

from typer.testing import CliRunner

from app.business.ops import auto_propose_strategy_change, build_column_asset, build_strategy_output
from app.main import app

runner = CliRunner()


def test_auto_propose_strategy_change_reads_latest_inputs(tmp_path: Path):
    intel_insights = tmp_path / "data" / "intel" / "insights"
    intel_sales = tmp_path / "data" / "intel" / "sales"
    intel_comp = tmp_path / "data" / "intel" / "competitors"
    intel_insights.mkdir(parents=True)
    intel_sales.mkdir(parents=True)
    intel_comp.mkdir(parents=True)
    (intel_insights / "2026-04-20-week.md").write_text("# 本周经营输入复盘\n\n- 哪些内容更适合卖专栏\n- 继续放大高转化题材\n", encoding="utf-8")
    (intel_sales / "2026-04-20.md").write_text("# 专栏与转化记录\n\n- 专栏: CSDN专栏增长\n- 指标: click\n- 数值: 19\n", encoding="utf-8")
    (intel_comp / "2026-04-20.md").write_text("# 对标账号与优秀案例\n\n- 观察: 同类专栏用案例拆解驱动转化\n", encoding="utf-8")

    build_column_asset(
        date="2026-04-20",
        account="技术小甜甜",
        column="CSDN专栏增长",
        goal="补齐转化链",
        existing_topics=["起号最小闭环"],
        gap_topics=["免费文如何自然导向专栏"],
        topic_roles=["转化题"],
        competitor_references=["同类专栏案例"],
        base_dir=tmp_path,
    )
    build_strategy_output(
        date="2026-04-19",
        account="技术小甜甜",
        stage_goal="建立转化基线",
        target_column="CSDN专栏增长",
        strategy_summary="当前以引流题为主",
        inputs=["旧策略输入"],
        adjustments=["旧策略调整"],
        competitor_insights=["旧竞品启发"],
        base_dir=tmp_path,
    )

    result = auto_propose_strategy_change(
        date="2026-04-21",
        account="技术小甜甜",
        stage_goal="提升专栏转化",
        target_column="CSDN专栏增长",
        base_dir=tmp_path,
    )

    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["status"] == "pending_approval"
    assert payload["current_summary"] == "当前以引流题为主"
    assert any("sales" in item or "专栏" in item for item in payload["source_signals"])
    assert any("空缺" in item or "专栏资产" in item or "当前专栏" in item for item in payload["expected_effects"] + payload["reasons"])


def test_auto_propose_strategy_change_cli(tmp_path: Path):
    intel_insights = tmp_path / "data" / "intel" / "insights"
    intel_insights.mkdir(parents=True)
    (intel_insights / "2026-04-20-week.md").write_text("# 本周经营输入复盘\n\n- 继续放大高转化题材\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "auto-propose-strategy-change",
            "--date", "2026-04-21",
            "--account", "技术小甜甜",
            "--stage-goal", "提升专栏转化",
            "--target-column", "CSDN专栏增长",
            "--base-dir", str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Auto strategy proposal saved" in result.output
