import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.intel.full_account_capture import parse_public_column_page, save_full_account_capture
from app.ops.new_account_mvp_planner import plan_new_account_daily_mvp

runner = CliRunner()


SAMPLE_PUBLIC_HTML = """
<html>
  <body>
    <h3 class="column_title oneline">AI实践-Dify专栏</h3>
    <span class="column_text_desc">聚焦Dify工作流、知识库、Agent、API 集成</span>
    <span class="column_data">文章数：191 文章阅读量：131464 文章收藏量：66</span>
    <ul class="column_article_list">
      <li>
        <div class="column_article_title"><h2 class="title">[Dify实战] 招投标标书智能生成：模板套用 + 风险校验</h2></div>
        <div class="column_article_desc">desc1</div>
        <div class="column_article_data"><span class="article-type">原创</span><span class="status">2026-03-26 11:39:00</span><span>466阅读</span></div>
        <a href="https://blog.csdn.net/sheepForTest/article/details/156000001">阅读全文</a>
      </li>
      <li>
        <div class="column_article_title"><h2 class="title">[Dify实战] 设计评审记录自动整理与问题追踪</h2></div>
        <div class="column_article_desc">desc2</div>
        <div class="column_article_data"><span class="article-type">原创</span><span class="status">2026-03-24 15:11:33</span><span>282阅读</span></div>
        <a href="https://blog.csdn.net/sheepForTest/article/details/156000002">阅读全文</a>
      </li>
    </ul>
  </body>
</html>
"""


def test_parse_public_column_page_extracts_column_meta_and_articles():
    result = parse_public_column_page(
        html=SAMPLE_PUBLIC_HTML,
        canonical_url="https://blog.csdn.net/sheepfortest/category_12947815.html",
        page_no=1,
    )

    assert result["column_title"] == "AI实践-Dify专栏"
    assert result["article_count_declared"] == 191
    assert len(result["articles"]) == 2
    assert result["articles"][0]["title"] == "[Dify实战] 招投标标书智能生成：模板套用 + 风险校验"
    assert result["articles"][1]["publish_time"] == "2026-03-24 15:11:33"


def test_parse_public_column_page_can_detect_verification_page():
    html = "<html><body><div>请完成下方验证后继续访问</div><div>点击按钮进行验证</div></body></html>"
    result = parse_public_column_page(
        html=html,
        canonical_url="https://blog.csdn.net/sheepfortest/category_12947815.html",
        page_no=1,
    )
    assert result["verification_detected"] is True
    assert result["articles"] == []


def _sample_full_capture() -> dict:
    return {
        "date": "2026-04-21",
        "account": "技术小甜甜",
        "captured_at": "2026-04-21T15:00:00Z",
        "columns": [
            {
                "title": "AI实践-Dify专栏",
                "public_url": "https://blog.csdn.net/sheepfortest/category_12947815.html",
                "price": 69.9,
                "article_count": 191,
                "status": "已上架",
                "articles": [
                    {"title": "[Dify实战] 招投标标书智能生成：模板套用 + 风险校验", "publish_time": "2026-03-26 11:39:00"},
                    {"title": "[Dify实战] 设计评审记录自动整理与问题追踪", "publish_time": "2026-03-24 15:11:33"},
                ],
            },
            {
                "title": "企业级AI落地实战：从模型部署到应用系统",
                "public_url": "https://blog.csdn.net/sheepfortest/category_13138265.html",
                "price": 9.9,
                "article_count": 11,
                "status": "已上架",
                "articles": [
                    {"title": "[企业AI落地] 使用 Ollama 搭建本地大模型服务实践（从0到1完整指南）", "publish_time": "2026-04-05 14:36:45"},
                    {"title": "[AI架构] 企业级 AI 应用系统的典型技术架构解析（从单点能力到生产级平台）", "publish_time": "2026-03-31 09:49:03"},
                ],
            },
        ],
    }


def test_plan_new_account_daily_mvp_prefers_two_distinct_columns(tmp_path: Path):
    capture_path = save_full_account_capture(
        date="2026-04-21",
        account="技术小甜甜",
        capture=_sample_full_capture(),
        base_dir=tmp_path,
    )["json_path"]

    result = plan_new_account_daily_mvp(
        date="2026-04-21",
        account="技术小甜甜",
        capture_path=capture_path,
        base_dir=tmp_path,
    )

    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["slot_count"] == 2
    columns = [slot["column"] for slot in payload["slots"]]
    assert len(set(columns)) == 2
    titles = [slot["title"] for slot in payload["slots"]]
    assert "[Dify实战] 招投标标书智能生成：模板套用 + 风险校验" not in titles
    assert any("Dify" in title for title in titles)
    assert any("企业AI" in title or "内网" in title or "推理" in title for title in titles)
    assert all("基于历史内容延续的下一篇实战题" not in title for title in titles)


def test_plan_new_account_daily_mvp_cli_writes_plan(tmp_path: Path):
    capture_path = save_full_account_capture(
        date="2026-04-21",
        account="技术小甜甜",
        capture=_sample_full_capture(),
        base_dir=tmp_path,
    )["json_path"]

    result = runner.invoke(
        app,
        [
            "plan-new-account-daily-mvp",
            "--date",
            "2026-04-21",
            "--account",
            "技术小甜甜",
            "--capture-path",
            str(capture_path),
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "New-account daily MVP plan saved" in result.output
