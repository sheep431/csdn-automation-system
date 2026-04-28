from pathlib import Path

from typer.testing import CliRunner

from app.business.ops import build_column_asset, build_strategy_output, create_topic_brief
from app.main import app

runner = CliRunner()


def test_build_strategy_output_writes_standard_artifacts(tmp_path: Path):
    result = build_strategy_output(
        date="2026-04-20",
        account="技术小甜甜",
        stage_goal="提升专栏转化率",
        target_column="CSDN专栏增长",
        strategy_summary="优先实操避坑和可直接导向专栏的题型",
        inputs=["周报显示专栏点击提高", "最近反馈偏好更具体"],
        adjustments=["减少纯概念题", "增加引流到转化的桥接题"],
        competitor_insights=["同类专栏用案例拆解带动转化"],
        base_dir=tmp_path,
    )

    assert result["json_path"].exists()
    assert result["md_path"].exists()
    content = result["md_path"].read_text(encoding="utf-8")
    assert "选题策略输出" in content
    assert "提升专栏转化率" in content
    assert "同类专栏用案例拆解带动转化" in content


def test_build_column_asset_writes_inventory_and_gap_map(tmp_path: Path):
    result = build_column_asset(
        date="2026-04-20",
        account="技术小甜甜",
        column="CSDN专栏增长",
        goal="补齐从起号到转化的主题缺口",
        existing_topics=["起号最小闭环", "发文基础设置"],
        gap_topics=["免费文如何自然导向专栏", "专栏页转化设计"],
        topic_roles=["引流题", "信任题", "转化题"],
        competitor_references=["某同类专栏把案例和CTA捆绑"],
        base_dir=tmp_path,
    )

    assert result["json_path"].exists()
    assert result["md_path"].exists()
    content = result["md_path"].read_text(encoding="utf-8")
    assert "专栏资产与空缺图" in content
    assert "起号最小闭环" in content
    assert "免费文如何自然导向专栏" in content


def test_plan_topic_can_reference_strategy_and_column_assets(tmp_path: Path):
    strategy = build_strategy_output(
        date="2026-04-20",
        account="技术小甜甜",
        stage_goal="提升专栏转化率",
        target_column="CSDN专栏增长",
        strategy_summary="优先桥接免费文到专栏的实操题",
        inputs=["最近专栏点击上升"],
        adjustments=["增加转化桥接题"],
        competitor_insights=["同类专栏用问题清单引流"],
        base_dir=tmp_path,
    )
    column_asset = build_column_asset(
        date="2026-04-20",
        account="技术小甜甜",
        column="CSDN专栏增长",
        goal="补齐转化链路",
        existing_topics=["起号最小闭环"],
        gap_topics=["免费文导向专栏"],
        topic_roles=["转化题"],
        competitor_references=["同类专栏结构"],
        base_dir=tmp_path,
    )

    path = create_topic_brief(
        date="2026-04-20",
        account="技术小甜甜",
        title="免费文如何自然引导用户进入专栏",
        audience="想提高专栏转化的 CSDN 作者",
        column="CSDN专栏增长",
        angle="从免费文布局到专栏承接",
        value="补上转化链路空缺",
        cta="引导进入专栏页看完整转化设计",
        source_inputs=["intel 周报", "竞品专栏拆解"],
        why_now="当前正处于转化链路补齐阶段",
        strategy_path=strategy["md_path"],
        column_asset_path=column_asset["md_path"],
        base_dir=tmp_path,
    )

    content = path.read_text(encoding="utf-8")
    assert "策略输出" in content
    assert "专栏资产" in content


def test_strategy_and_column_cli_commands(tmp_path: Path):
    result_strategy = runner.invoke(
        app,
        [
            "build-strategy-output",
            "--date", "2026-04-20",
            "--account", "技术小甜甜",
            "--stage-goal", "提升专栏转化率",
            "--target-column", "CSDN专栏增长",
            "--strategy-summary", "优先实操转化题",
            "--input-item", "最近反馈偏好具体题",
            "--adjustment", "减少纯概念题",
            "--competitor-insight", "同类专栏偏案例驱动",
            "--base-dir", str(tmp_path),
        ],
    )
    assert result_strategy.exit_code == 0
    assert "Strategy output saved" in result_strategy.output

    result_column = runner.invoke(
        app,
        [
            "build-column-asset",
            "--date", "2026-04-20",
            "--account", "技术小甜甜",
            "--column", "CSDN专栏增长",
            "--goal", "补齐专栏空缺",
            "--existing-topic", "起号最小闭环",
            "--gap-topic", "专栏转化桥接",
            "--topic-role", "转化题",
            "--competitor-reference", "同类专栏案例",
            "--base-dir", str(tmp_path),
        ],
    )
    assert result_column.exit_code == 0
    assert "Column asset saved" in result_column.output
