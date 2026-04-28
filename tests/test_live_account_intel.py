import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.intel.live_accounts import save_live_account_snapshot, sync_topic_usage_from_live_snapshot

runner = CliRunner()


def _sample_live_snapshot() -> dict:
    return {
        "captured_at": "2026-04-21T10:00:00Z",
        "pages": [
            {
                "label": "专栏/专辑列表页",
                "url": "https://mp.csdn.net/columns",
                "title": "专栏列表",
                "headings": ["AI实践-Dify专栏", "技术前沿每日速读"],
                "tables": [
                    {
                        "headers": ["专栏", "文章数", "最近更新"],
                        "rows": [
                            ["AI实践-Dify专栏", "183", "2026-04-21"],
                            ["技术前沿每日速读", "0", "2023-07-01"],
                        ],
                    }
                ],
            },
            {
                "label": "历史题目/文章列表页",
                "url": "https://mp.csdn.net/articles",
                "title": "历史文章",
                "headings": ["最近发布"],
                "tables": [
                    {
                        "headers": ["标题", "发布时间"],
                        "rows": [
                            ["[Dify实战] 多轮对话状态管理：上下文保持与槽位填充", "2026-04-21 09:30"],
                            ["[Dify实战] 用 Dify 打造“会议纪要+行动项”一键落地助手", "2026-04-20 09:00"],
                        ],
                    }
                ],
            },
        ],
    }


def _batch_with_topics(tmp_path: Path) -> Path:
    batch_dir = tmp_path / "data" / "business" / "topic_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_path = batch_dir / "topic-batch_20260421090000.json"
    payload = {
        "account": "技术小甜甜",
        "generated_at": "2026-04-21T09:00:00Z",
        "batch_strategy": "围绕 Dify 主专栏生成",
        "writing_order": ["[Dify实战] 多轮对话状态管理：上下文保持与槽位填充"],
        "topics": [
            {
                "number": 1,
                "title": "[Dify实战] 多轮对话状态管理：上下文保持与槽位填充",
                "audience": "Dify 开发者",
                "account": "技术小甜甜",
                "column": "AI实践-Dify专栏",
                "reason": "补状态管理缺口",
                "expected_value": "承接后续 RAG 题",
                "why_now": "主专栏下一阶段核心题",
                "cta": "继续看 RAG 进阶",
                "role": "信任题",
                "risk": "需要案例支撑",
                "priority": "主推",
            },
            *[
                {
                    "number": idx,
                    "title": f"占位题 {idx}",
                    "audience": "Dify 开发者",
                    "account": "技术小甜甜",
                    "column": "AI实践-Dify专栏",
                    "reason": f"理由 {idx}",
                    "expected_value": f"价值 {idx}",
                    "why_now": f"为什么现在 {idx}",
                    "cta": f"CTA {idx}",
                    "role": "引流题" if idx <= 6 else "备用题",
                    "risk": f"风险 {idx}",
                    "priority": "主推" if idx <= 6 else "备用",
                }
                for idx in range(2, 9)
            ],
        ],
    }
    payload["topics"][6]["role"] = "转化题"
    payload["topics"][7]["role"] = "转化题"
    batch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return batch_path


def test_save_live_account_snapshot_writes_json_and_markdown_summary(tmp_path: Path):
    result = save_live_account_snapshot(
        date="2026-04-21",
        account="技术小甜甜",
        snapshot=_sample_live_snapshot(),
        base_dir=tmp_path,
    )

    assert result["json_path"].exists()
    assert result["md_path"].exists()

    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["account"] == "技术小甜甜"
    assert payload["article_titles"][0] == "[Dify实战] 多轮对话状态管理：上下文保持与槽位填充"

    content = result["md_path"].read_text(encoding="utf-8")
    assert "账号实时采集快照" in content
    assert "AI实践-Dify专栏" in content
    assert "多轮对话状态管理" in content


def test_save_live_account_snapshot_can_extract_article_titles_from_page_level_list_items(tmp_path: Path):
    snapshot = {
        "captured_at": "2026-04-21T10:00:00Z",
        "pages": [
            {
                "label": "历史题目/文章列表页",
                "url": "https://mp.csdn.net/mp_blog/manage/article",
                "title": "内容管理-CSDN创作中心",
                "headings": ["创作中心"],
                "tables": [],
                "article_titles": [
                    "[AI] 企业内网部署大模型的三种常见方案：从“能用”到“好用”的技术选型指南",
                    "[Dify实战] 招投标标书智能生成：模板套用 + 风险校验",
                ],
            }
        ],
    }

    result = save_live_account_snapshot(
        date="2026-04-21",
        account="技术小甜甜",
        snapshot=snapshot,
        base_dir=tmp_path,
    )

    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["article_titles"] == [
        "[AI] 企业内网部署大模型的三种常见方案：从“能用”到“好用”的技术选型指南",
        "[Dify实战] 招投标标书智能生成：模板套用 + 风险校验",
    ]


def test_sync_topic_usage_from_live_snapshot_marks_matching_titles_published(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)
    snapshot_result = save_live_account_snapshot(
        date="2026-04-21",
        account="技术小甜甜",
        snapshot=_sample_live_snapshot(),
        base_dir=tmp_path,
    )

    result = sync_topic_usage_from_live_snapshot(
        date="2026-04-21",
        account="技术小甜甜",
        snapshot_path=snapshot_result["json_path"],
        base_dir=tmp_path,
    )

    assert result["ledger_path"].exists()
    ledger = json.loads(result["ledger_path"].read_text(encoding="utf-8"))
    matched = next(entry for entry in ledger["entries"] if entry["title"] == "[Dify实战] 多轮对话状态管理：上下文保持与槽位填充")
    assert matched["status"] == "published"
    assert result["published_count"] == 1
    assert batch_path.exists()


def test_import_and_sync_live_snapshot_cli(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)
    raw_path = tmp_path / "raw-live.json"
    raw_path.write_text(json.dumps(_sample_live_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")

    import_result = runner.invoke(
        app,
        [
            "import-csdn-live-snapshot",
            "--date",
            "2026-04-21",
            "--account",
            "技术小甜甜",
            "--snapshot-json-path",
            str(raw_path),
            "--base-dir",
            str(tmp_path),
        ],
    )
    assert import_result.exit_code == 0
    assert "Live CSDN snapshot saved" in import_result.output

    snapshot_path = tmp_path / "data" / "intel" / "accounts" / "2026-04-21_技术小甜甜_live.json"
    assert snapshot_path.exists()

    sync_result = runner.invoke(
        app,
        [
            "sync-published-from-live",
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
    assert sync_result.exit_code == 0
    assert "Live publish sync finished" in sync_result.output
    assert batch_path.exists()
