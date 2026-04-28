from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.execution.ops import execute_topic_pipeline

runner = CliRunner()


def test_execute_topic_pipeline_creates_business_process_and_state_artifacts(tmp_path: Path):
    result = execute_topic_pipeline(
        date="2026-04-19",
        account="技术小甜甜",
        title="Python 字典去重的 3 种写法",
        audience="刚学 Python 的新手",
        column="Python 入门系列",
        angle="从错误示例到可直接复制的正确写法",
        value="能直接解决新手常见去重问题，容易形成系列化内容",
        cta="在专栏页继续看集合、列表推导式和字典的实战组合",
        body_markdown="# Python 字典去重的 3 种写法\n\n正文内容\n\n- 示例 1\n- 示例 2",
        tags=["Python", "字典", "新手"],
        why_now="新号需要一篇可以直接执行的教程题",
        source_inputs=["第 0 层经营输入", "用户明确要求先做最小闭环"],
        base_dir=tmp_path,
    )

    assert result["business_brief_path"].exists()
    assert result["workflow_flow_path"].exists()
    assert result["workflow_task_path"].exists()
    assert result["state_snapshot_path"].exists()

    business_content = result["business_brief_path"].read_text(encoding="utf-8")
    assert "业务层选题决策" in business_content
    assert "Python 字典去重的 3 种写法" in business_content

    flow_content = result["workflow_flow_path"].read_text(encoding="utf-8")
    assert "流程层执行单" in flow_content
    assert "Python 入门系列" in flow_content

    task_content = result["workflow_task_path"].read_text(encoding="utf-8")
    assert "process_workflow" in task_content
    assert "waiting_review" in task_content

    snapshot_content = result["state_snapshot_path"].read_text(encoding="utf-8")
    assert "状态快照" in snapshot_content
    assert "topic" in snapshot_content
    assert "draft" in snapshot_content


def test_execute_topic_pipeline_records_state_history(tmp_path: Path):
    result = execute_topic_pipeline(
        date="2026-04-19",
        account="技术小甜甜",
        title="如何给 CSDN 文章配图不踩坑",
        audience="想快速上手发文的新手博主",
        column="CSDN 实战系列",
        angle="直接给出可复制的步骤和检查清单",
        value="这类内容可以直接转成教程型流量题",
        cta="引导读者继续看专栏里的完整发文流程",
        body_markdown="# 如何给 CSDN 文章配图不踩坑\n\n正文内容",
        tags=["CSDN", "配图"],
        why_now="当前正在搭建自动化发文闭环，需要补齐实操步骤",
        source_inputs=["第 0 层经营输入"],
        base_dir=tmp_path,
    )

    topic_history = tmp_path / "data" / "state" / "history" / "topic" / f"{result['topic_id']}.jsonl"
    draft_history = tmp_path / "data" / "state" / "history" / "draft" / f"{result['draft_id']}.jsonl"

    assert topic_history.exists()
    assert draft_history.exists()
    assert len(topic_history.read_text(encoding="utf-8").splitlines()) == 1
    assert len(draft_history.read_text(encoding="utf-8").splitlines()) == 1


def test_execute_topic_cli_creates_all_artifacts(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "execute-topic",
            "--date",
            "2026-04-19",
            "--account",
            "技术小甜甜",
            "--title",
            "Python 字典去重的 3 种写法",
            "--audience",
            "刚学 Python 的新手",
            "--column",
            "Python 入门系列",
            "--angle",
            "从错误示例到可直接复制的正确写法",
            "--value",
            "能直接解决新手常见去重问题，容易形成系列化内容",
            "--cta",
            "在专栏页继续看集合、列表推导式和字典的实战组合",
            "--body-markdown",
            "# Python 字典去重的 3 种写法\n\n正文内容",
            "--tag",
            "Python",
            "--tag",
            "字典",
            "--tag",
            "新手",
            "--why-now",
            "新号需要一篇可以直接执行的教程题",
            "--source-input",
            "第 0 层经营输入",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert (tmp_path / "data" / "business" / "topic_briefs").exists()
    assert (tmp_path / "data" / "process" / "flows").exists()
    assert (tmp_path / "data" / "tasks" / "pending").exists()
    assert (tmp_path / "data" / "state" / "snapshots").exists()
