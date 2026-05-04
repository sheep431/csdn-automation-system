import json
from pathlib import Path

from typer.testing import CliRunner

from app.business.ops import _collect_topic_library_dashboard_rows, build_baseline_column_assets_from_full_capture, build_baseline_topic_libraries_from_full_capture, build_column_asset, build_strategy_output, build_topic_library_dashboard, create_topic_brief
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


def test_build_baseline_column_assets_from_full_capture_creates_per_column_assets(tmp_path: Path):
    capture = tmp_path / "full.json"
    capture.write_text(
        """
{
  "columns": [
    {
      "title": "AI实践-Dify专栏",
      "description": "聚焦 Dify 工作流、知识库、Agent",
      "articles": [
        {"title": "Dify 入口篇"},
        {"title": "Dify 工作流案例篇"}
      ]
    },
    {
      "title": "技术前沿每日速读",
      "description": "AI 热点速读",
      "articles": [
        {"title": "本周 AI 热点 1"}
      ]
    }
  ]
}
        """.strip(),
        encoding="utf-8",
    )

    result = build_baseline_column_assets_from_full_capture(
        date="2026-04-28",
        account="技术小甜甜",
        capture_path=capture,
        base_dir=tmp_path,
    )

    assert result["created_count"] == 2
    first = result["assets"][0]
    assert "AI实践-Dify专栏" in first["column"]
    md = Path(first["md_path"]).read_text(encoding="utf-8")
    assert "专栏资产与空缺图" in md
    assert "Dify 入口篇" in md
    assert "知识库问答结构是否形成系列" in md



def test_build_baseline_topic_libraries_from_full_capture_creates_unused_candidates(tmp_path: Path):
    capture = tmp_path / "full.json"
    article_entries = ",\n".join(
        f'        {{"title": "Dify 基线文章 {idx:02d}"}}' for idx in range(1, 36)
    )
    capture.write_text(
        f"""
{{
  "columns": [
    {{
      "title": "AI实践-Dify专栏",
      "description": "聚焦 Dify 工作流、知识库、Agent",
      "articles": [
{article_entries}
      ]
    }}
  ]
}}
        """.strip(),
        encoding="utf-8",
    )

    result = build_baseline_topic_libraries_from_full_capture(
        date="2026-04-28",
        account="技术小甜甜",
        capture_path=capture,
        base_dir=tmp_path,
    )

    assert result["created_count"] == 1
    assert result["skipped_count"] == 0
    library = Path(result["libraries"][0]["json_path"])
    payload = json.loads(library.read_text(encoding="utf-8"))
    assert payload["column"] == "AI实践-Dify专栏"
    assert len(payload["existing_topics"]) == 35
    assert payload["existing_topics"][0] == "Dify 基线文章 01"
    assert payload["existing_topics"][-1] == "Dify 基线文章 35"
    assert payload["modules"]
    assert any(module["candidate_topics"] for module in payload["modules"])
    assert payload["modules"][0]["candidate_topics"][0]["status"] == "unused"
    assert payload["modules"][0]["candidate_topics"][0]["candidate_id"]



def test_build_baseline_topic_libraries_skips_only_deprecated_columns(tmp_path: Path):
    capture = tmp_path / "full_deprecated.json"
    capture.write_text(
        json.dumps(
            {
                "columns": [
                    {"title": "活动专栏", "description": "desc", "articles": []},
                    {"title": "停刊专栏", "description": "desc", "articles": []},
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    state_dir = tmp_path / "data" / "state" / "ledger" / "column"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "技术小甜甜__停刊专栏.json").write_text(
        json.dumps(
            {
                "object_type": "column",
                "object_id": "技术小甜甜__停刊专栏",
                "state": "deprecated",
                "attributes": {"account": "技术小甜甜", "column": "停刊专栏"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = build_baseline_topic_libraries_from_full_capture(
        date="2026-04-28",
        account="技术小甜甜",
        capture_path=capture,
        base_dir=tmp_path,
    )

    assert result["created_count"] == 1
    assert result["libraries"][0]["column"] == "活动专栏"
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["column"] == "停刊专栏"



def test_build_baseline_topic_libraries_preserves_existing_candidate_status_on_recalibration(tmp_path: Path):
    capture_v1 = tmp_path / "full_v1.json"
    capture_v1.write_text(
        json.dumps(
            {
                "columns": [
                    {
                        "title": "AI实践-Dify专栏",
                        "description": "聚焦 Dify 工作流、知识库、Agent",
                        "articles": [{"title": "旧发布 1"}],
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    build_baseline_topic_libraries_from_full_capture(
        date="2026-04-28",
        account="技术小甜甜",
        capture_path=capture_v1,
        base_dir=tmp_path,
    )

    first_path = tmp_path / "data" / "business" / "topic_libraries" / "2026-04-28_技术小甜甜_ai实践-dify专栏.json"
    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    first_payload["modules"][0]["candidate_topics"][0]["status"] = "approved"
    first_payload["modules"][0]["candidate_topics"][0]["notes"] = "人工已确认"
    first_path.write_text(json.dumps(first_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    capture_v2 = tmp_path / "full_v2.json"
    capture_v2.write_text(
        json.dumps(
            {
                "columns": [
                    {
                        "title": "AI实践-Dify专栏",
                        "description": "聚焦 Dify 工作流、知识库、Agent",
                        "articles": [{"title": "旧发布 1"}, {"title": "新发布 2"}],
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    build_baseline_topic_libraries_from_full_capture(
        date="2026-04-29",
        account="技术小甜甜",
        capture_path=capture_v2,
        base_dir=tmp_path,
    )

    second_path = tmp_path / "data" / "business" / "topic_libraries" / "2026-04-29_技术小甜甜_ai实践-dify专栏.json"
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    first_candidate = second_payload["modules"][0]["candidate_topics"][0]
    assert first_candidate["status"] == "approved"
    assert first_candidate["notes"] == "人工已确认"
    assert second_payload["existing_topics"] == ["旧发布 1", "新发布 2"]



def test_build_topic_library_dashboard_writes_html_panel(tmp_path: Path):
    (tmp_path / "data" / "business" / "topic_libraries").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "business" / "topic_usage").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "state" / "ledger" / "column").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "business" / "topic_usage" / "topic_usage_ledger.json").write_text(
        json.dumps({"entries": [{"account": "技术小甜甜", "column": "AI实践-Dify专栏", "status": "published", "title": "新发题"}]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (tmp_path / "data" / "business" / "topic_libraries" / "2026-04-29_技术小甜甜_ai实践-dify专栏.json").write_text(
        json.dumps(
            {
                "date": "2026-04-29",
                "account": "技术小甜甜",
                "column": "AI实践-Dify专栏",
                "existing_topics": ["旧题1", "旧题2"],
                "library_strategy": "先消耗结构化基线题库，再在空缺上补结构或挖深度。",
                "modules": [
                    {
                        "name": "Dify 基础认知与入口价值",
                        "status": "covered",
                        "candidate_topics": [{"title": "新题1", "status": "unused"}],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "state" / "ledger" / "column" / "技术小甜甜__ai实践-dify专栏.json").write_text(
        json.dumps({"state": "active_revenue", "attributes": {"account": "技术小甜甜", "role": "flagship_revenue", "column": "AI实践-Dify专栏"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rows = _collect_topic_library_dashboard_rows(account="技术小甜甜", base_dir=tmp_path)
    assert rows[0]["published_count"] == 3
    assert rows[0]["pending_count"] == 1

    output = tmp_path / "dashboard.html"
    path = build_topic_library_dashboard(
        account="技术小甜甜",
        base_dir=tmp_path,
        output_path=output,
        action_config={"calibrate_path": "/actions/calibrate", "can_calibrate": True, "calibrate_label": "校准 baseline"},
    )
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "技术小甜甜 专栏概览" in content
    assert "AI实践-Dify专栏" in content
    assert "active_revenue" in content
    assert "总专栏数" in content
    assert "旧题1" in content
    assert "新发题" in content
    assert "校准 baseline" in content
    assert "/actions/calibrate" in content



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

    capture = tmp_path / "full.json"
    capture.write_text('{"columns": [{"title": "AI实践-Dify专栏", "description": "聚焦 Dify", "articles": [{"title": "Dify 入口篇"}]}]}', encoding="utf-8")
    result_baseline = runner.invoke(
        app,
        [
            "build-column-baseline-from-full",
            "--date", "2026-04-28",
            "--account", "技术小甜甜",
            "--capture-path", str(capture),
            "--base-dir", str(tmp_path),
        ],
    )
    assert result_baseline.exit_code == 0
    assert "Column baseline assets saved" in result_baseline.output

    result_library = runner.invoke(
        app,
        [
            "build-topic-library-baseline-from-full",
            "--date", "2026-04-28",
            "--account", "技术小甜甜",
            "--capture-path", str(capture),
            "--base-dir", str(tmp_path),
        ],
    )
    assert result_library.exit_code == 0
    assert "Topic library baseline saved" in result_library.output
