from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.process.ops import create_workflow_manifest, materialize_workflow_task, review_process

runner = CliRunner()


def test_create_workflow_manifest_writes_flow_note(tmp_path: Path):
    brief_path = tmp_path / "data" / "business" / "topic_briefs" / "2026-04-19_python.md"
    brief_path.parent.mkdir(parents=True)
    brief_path.write_text(
        "# 业务层选题决策：Python 字典去重\n\n- 账号: 技术小甜甜\n- 目标读者: 新手\n- 专栏/栏目: Python 入门系列\n",
        encoding="utf-8",
    )

    path = create_workflow_manifest(
        date="2026-04-19",
        account="技术小甜甜",
        title="Python 字典去重的 3 种写法",
        column="Python 入门系列",
        body_markdown="# Python 字典去重的 3 种写法\n\n正文内容",
        tags=["Python", "字典", "新手"],
        source_brief_path=brief_path,
        why_now="新号需要一篇可以直接执行的教程题",
        base_dir=tmp_path,
    )

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "流程层执行单" in content
    assert "## 主流程" in content
    assert "## 异常分支" in content
    assert "Python 字典去重的 3 种写法" in content
    assert "业务层选题决策" in content


def test_materialize_workflow_task_writes_pending_task_json(tmp_path: Path):
    path = materialize_workflow_task(
        date="2026-04-19",
        account="技术小甜甜",
        title="Python 字典去重的 3 种写法",
        body_markdown="# Python 字典去重的 3 种写法\n\n正文内容",
        tags=["Python", "字典", "新手"],
        column="Python 入门系列",
        source_brief_path=None,
        why_now=None,
        base_dir=tmp_path,
    )

    assert path.exists()
    payload = path.read_text(encoding="utf-8")
    assert "process_profile" in payload
    assert "requires_human_review" in payload
    assert "review_status" in payload
    assert "Python 字典去重的 3 种写法" in payload


def test_review_process_builds_summary_from_flow_notes(tmp_path: Path):
    flow_dir = tmp_path / "data" / "process" / "flows"
    flow_dir.mkdir(parents=True)
    (flow_dir / "2026-04-19_python.md").write_text(
        "# 流程层执行单：Python 字典去重\n\n- 账号: 技术小甜甜\n- 主题: Python 字典去重\n- 状态: waiting_review\n",
        encoding="utf-8",
    )

    path = review_process(date="2026-04-19", base_dir=tmp_path, account="技术小甜甜")

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "流程层复盘" in content
    assert "## 流程概览" in content
    assert "Python 字典去重" in content
    assert "## 异常与补救" in content


def test_plan_workflow_cli_creates_flow_and_pending_task(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "plan-workflow",
            "--date",
            "2026-04-19",
            "--account",
            "技术小甜甜",
            "--title",
            "Python 字典去重的 3 种写法",
            "--body-markdown",
            "# Python 字典去重的 3 种写法\n\n正文内容",
            "--column",
            "Python 入门系列",
            "--tag",
            "Python",
            "--tag",
            "字典",
            "--tag",
            "新手",
            "--source-brief-path",
            str(tmp_path / "data" / "business" / "topic_briefs" / "2026-04-19_python.md"),
            "--why-now",
            "新号需要一篇教程题",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    flow_files = list((tmp_path / "data" / "process" / "flows").glob("*.md"))
    task_files = list((tmp_path / "data" / "tasks" / "pending").glob("*.json"))
    assert len(flow_files) == 1
    assert len(task_files) == 1
    flow_content = flow_files[0].read_text(encoding="utf-8")
    assert "流程层执行单" in flow_content
    assert "Python 字典去重的 3 种写法" in flow_content
