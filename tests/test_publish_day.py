import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.ops.publish_day import prepare_publish_day

runner = CliRunner()


def _sample_plan() -> dict:
    return {
        "date": "2026-04-21",
        "slots": [
            {
                "slot_id": "2026-04-21-old-traffic-1",
                "account_profile": "old-traffic",
                "account_name": "踏雪无痕老爷子",
                "goal": "traffic",
                "title": "[AI] 新手最容易误解的 3 个提示词写作误区",
                "topic": "提示词避坑",
                "audience": "想用 AI 提升写作效率的新手作者",
                "column": "AI 写作避坑",
                "angle": "用真实误区示例拆解为什么文章容易写空",
                "value": "兼顾搜索流量和完读率，适合老号做吸粉测试",
                "cta": "文末引导读者领取提示词自检清单",
                "why_now": "AI 写作仍是持续高热话题，老号适合承接泛搜索流量",
                "keywords": ["AI写作", "提示词", "避坑"],
                "outline": [
                    "为什么同样写 AI 主题，有人能拿收藏有人拿不到",
                    "3 个常见误区 + 错误示例 + 改法",
                    "一份可直接套用的自检清单"
                ],
                "notes": "老号偏流量题"
            },
            {
                "slot_id": "2026-04-21-new-main-1",
                "account_profile": "new-main",
                "account_name": "技术小甜甜",
                "goal": "revenue",
                "title": "[CSDN运营] 一篇技术文从标题到 CTA 的完整模板",
                "topic": "技术文模板",
                "audience": "想稳定更新 CSDN 并逐步导向专栏的技术作者",
                "column": "CSDN 内容增长",
                "angle": "直接提供可复制模板和拆解示例",
                "value": "适合新号建立信任，也能承接后续专栏转化",
                "cta": "引导读者继续查看专栏里的系列模板",
                "why_now": "今天就需要出稿，新号优先发强实操模板题",
                "keywords": ["CSDN", "写作模板", "CTA"],
                "outline": [
                    "高质量技术文为什么总能被收藏",
                    "标题-开头-主体-结尾 CTA 的标准模板",
                    "一个完整案例"
                ]
            }
        ]
    }


def test_prepare_publish_day_creates_board_packets_and_manifest(tmp_path: Path):
    plan = _sample_plan()

    result = prepare_publish_day(plan=plan, base_dir=tmp_path)

    assert result["board_path"].exists()
    assert result["manifest_json_path"].exists()
    assert result["manifest_md_path"].exists()
    assert result["column_allocation_json_path"].exists()
    assert result["column_allocation_md_path"].exists()
    assert len(result["packet_paths"]) == 2

    board = json.loads(result["board_path"].read_text(encoding="utf-8"))
    assert board["date"] == "2026-04-21"
    assert board["slot_count"] == 2
    assert board["slots"][0]["status"] == "drafting_ready"
    assert board["slots"][0]["article_source"] == "packet"

    packet = json.loads(result["packet_paths"][0].read_text(encoding="utf-8"))
    assert packet["title"].startswith("[AI]")
    assert "2000" in packet["writing_prompt"]
    assert "结构化总结" in packet["writing_prompt"]
    assert packet["draft_markdown_path"]
    assert Path(packet["draft_markdown_path"]).exists()

    draft_markdown = Path(packet["draft_markdown_path"]).read_text(encoding="utf-8")
    assert "## 一、问题背景" in draft_markdown
    assert "## 结构化总结" in draft_markdown

    allocation = json.loads(result["column_allocation_json_path"].read_text(encoding="utf-8"))
    assert allocation["allocation_count"] == 2
    assert allocation["allocations"][0]["column"] == "AI 写作避坑"


def test_prepare_publish_day_cli_writes_outputs(tmp_path: Path):
    plan_path = tmp_path / "publish-plan.json"
    plan_path.write_text(json.dumps(_sample_plan(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "prepare-publish-day",
            "--plan-json-path",
            str(plan_path),
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Publish-day package ready" in result.stdout

    manifest_path = tmp_path / "data" / "daily_publish" / "2026-04-21" / "publish-day_2026-04-21.json"
    assert manifest_path.exists()
