import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.business.live_topic_batch import plan_topic_batch_from_live

runner = CliRunner()


def _write_live_snapshot(tmp_path: Path) -> Path:
    snapshot_dir = tmp_path / "data" / "intel" / "accounts"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "2026-04-21_技术小甜甜_live.json"
    payload = {
        "date": "2026-04-21",
        "account": "技术小甜甜",
        "captured_at": "2026-04-21T10:00:00Z",
        "column_names": ["AI实践-Dify专栏", "技术前沿每日速读"],
        "article_titles": [
            "[Dify实战] 用Dify实现发布自动化：代码变更摘要与发布公告生成全流程解析",
            "[Dify实战] 用 Dify 打造“会议纪要+行动项”一键落地助手",
            "[Dify实战] 数据指标异常报警 + 原因分析机器人",
            "[Dify实战] 技术方案评审助手：自动生成评审大纲 + 风险清单",
            "[Dify实战] 产品手册自动编写助手：基于结构化输入一键生成",
        ],
        "pages": [],
    }
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot_path


def _write_full_capture_for_live_batch(tmp_path: Path) -> Path:
    snapshot_dir = tmp_path / "data" / "intel" / "accounts"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    full_path = snapshot_dir / "2026-04-21_技术小甜甜_full.json"
    payload = {
        "date": "2026-04-21",
        "account": "技术小甜甜",
        "captured_at": "2026-04-21T10:05:00Z",
        "columns": [
            {
                "title": "AI实践-Dify专栏",
                "price": 69.9,
                "article_count": 191,
                "metric_2": 248,
                "status": "已上架",
            },
            {
                "title": "企业级AI落地实战：从模型部署到应用系统",
                "price": 9.9,
                "article_count": 11,
                "metric_2": 5,
                "status": "已上架",
            },
            {
                "title": "技术前沿每日速读",
                "price": 0.0,
                "article_count": 9,
                "metric_2": 0,
                "status": "-",
            },
        ],
    }
    full_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return full_path


def test_plan_topic_batch_from_live_requires_real_snapshot_and_avoids_recent_titles(tmp_path: Path):
    snapshot_path = _write_live_snapshot(tmp_path)
    _write_full_capture_for_live_batch(tmp_path)

    business_strategy = tmp_path / "data" / "business" / "strategy_outputs"
    business_columns = tmp_path / "data" / "business" / "columns"
    intel_sales = tmp_path / "data" / "intel" / "sales"
    intel_feedback = tmp_path / "data" / "intel" / "feedback"
    business_strategy.mkdir(parents=True, exist_ok=True)
    business_columns.mkdir(parents=True, exist_ok=True)
    intel_sales.mkdir(parents=True, exist_ok=True)
    intel_feedback.mkdir(parents=True, exist_ok=True)

    (business_strategy / "2026-04-20_技术小甜甜_strategy.json").write_text(
        json.dumps({"account": "技术小甜甜", "target_column": "企业级AI落地实战：从模型部署到应用系统", "strategy_summary": "第二收益点优先承接企业AI落地专栏"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (business_columns / "2026-04-20_技术小甜甜_企业级ai落地实战：从模型部署到应用系统.md").write_text(
        "# 专栏资产与空缺图\n\n- 专栏: 企业级AI落地实战：从模型部署到应用系统\n- 当前空缺: 转化桥接\n- 点击信号: 最近专栏点击提升\n",
        encoding="utf-8",
    )
    (intel_sales / "2026-04-20.md").write_text(
        "# 专栏与转化记录\n\n- 专栏: 企业级AI落地实战：从模型部署到应用系统\n- 指标: click\n- 数值: 19\n",
        encoding="utf-8",
    )
    (intel_feedback / "2026-04-20.md").write_text(
        "# 用户反馈记录\n\n- 内容: 企业级AI落地实战：从模型部署到应用系统 这条线可以继续加权\n",
        encoding="utf-8",
    )

    state_dir = tmp_path / "data" / "state" / "ledger" / "column"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "技术小甜甜__企业级ai落地实战-从模型部署到应用系统.json").write_text(
        json.dumps(
            {
                "object_type": "column",
                "object_id": "技术小甜甜__企业级ai落地实战-从模型部署到应用系统",
                "state": "active_revenue",
                "attributes": {"account": "技术小甜甜", "column": "企业级AI落地实战：从模型部署到应用系统", "role": "secondary_revenue"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (state_dir / "技术小甜甜__技术前沿每日速读.json").write_text(
        json.dumps(
            {
                "object_type": "column",
                "object_id": "技术小甜甜__技术前沿每日速读",
                "state": "paused",
                "attributes": {"account": "技术小甜甜", "column": "技术前沿每日速读", "role": "traffic_support"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = plan_topic_batch_from_live(
        date="2026-04-21",
        account="技术小甜甜",
        snapshot_path=snapshot_path,
        base_dir=tmp_path,
    )

    assert result["json_path"].exists()
    assert result["md_path"].exists()

    batch = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert batch["account"] == "技术小甜甜"
    assert len(batch["topics"]) == 8
    assert any("live snapshot" in signal.lower() for signal in batch.get("source_signals", []))

    recent_titles = {
        "[Dify实战] 用Dify实现发布自动化：代码变更摘要与发布公告生成全流程解析",
        "[Dify实战] 用 Dify 打造“会议纪要+行动项”一键落地助手",
        "[Dify实战] 数据指标异常报警 + 原因分析机器人",
    }
    generated_titles = {topic["title"] for topic in batch["topics"]}
    assert recent_titles.isdisjoint(generated_titles)
    assert any("多轮对话状态管理" in title or "召回不全" in title for title in generated_titles)
    assert batch["topics"][0]["column"] == "AI实践-Dify专栏"
    assert batch["topics"][1]["column"] == "企业级AI落地实战：从模型部署到应用系统"
    assert any("different columns" in item for item in batch.get("changes_from_previous", []))
    scorer_signal = next(item for item in batch.get("source_signals", []) if item.startswith("secondary column scorer:"))
    assert "selected=企业级AI落地实战：从模型部署到应用系统" in scorer_signal
    assert "付费专栏" in scorer_signal
    assert "lifecycle: active_revenue" in scorer_signal
    assert "strategy match" in scorer_signal or "column asset match" in scorer_signal or "sales match" in scorer_signal or "feedback match" in scorer_signal


def test_plan_topic_batch_from_live_cli_writes_standard_batch(tmp_path: Path):
    snapshot_path = _write_live_snapshot(tmp_path)

    result = runner.invoke(
        app,
        [
            "plan-topic-batch-from-live",
            "--date",
            "2026-04-21",
            "--account",
            "技术小甜甜",
            "--snapshot-path",
            str(snapshot_path),
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Live topic batch saved" in result.output
    batch_path = tmp_path / "data" / "business" / "topic_batches" / "topic-batch_20260421100000.json"
    assert batch_path.exists()
