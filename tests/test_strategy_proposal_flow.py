from pathlib import Path
import json

from typer.testing import CliRunner

from app.business.ops import approve_strategy_change, propose_strategy_change
from app.main import app

runner = CliRunner()


def test_propose_strategy_change_writes_brief_files(tmp_path: Path):
    result = propose_strategy_change(
        date="2026-04-20",
        account="技术小甜甜",
        stage_goal="提高专栏转化",
        target_column="CSDN专栏增长",
        current_summary="当前以基础引流题为主",
        proposed_summary="增加免费文到专栏的桥接题比例",
        reasons=["最近专栏点击上升，但转化桥接不足"],
        expected_effects=["选题会更偏桥接型转化题"],
        risks=["过度转化会影响阅读体验"],
        source_signals=["sales 周报", "competitor 拆解"],
        base_dir=tmp_path,
    )

    assert result["json_path"].exists()
    assert result["md_path"].exists()
    md = result["md_path"].read_text(encoding="utf-8")
    assert "策略变更简报" in md
    assert "pending_approval" in md
    assert "最近专栏点击上升" in md


def test_approve_strategy_change_creates_official_strategy_output(tmp_path: Path):
    proposal = propose_strategy_change(
        date="2026-04-20",
        account="技术小甜甜",
        stage_goal="提高专栏转化",
        target_column="CSDN专栏增长",
        current_summary="当前以基础引流题为主",
        proposed_summary="增加免费文到专栏的桥接题比例",
        reasons=["最近专栏点击上升，但转化桥接不足"],
        expected_effects=["选题会更偏桥接型转化题"],
        risks=["过度转化会影响阅读体验"],
        source_signals=["sales 周报", "competitor 拆解"],
        base_dir=tmp_path,
    )

    result = approve_strategy_change(proposal_path=proposal["json_path"], base_dir=tmp_path)
    assert result["proposal_path"].exists()
    assert result["json_path"].exists()
    official = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert official["strategy_summary"] == "增加免费文到专栏的桥接题比例"
    updated_proposal = json.loads(result["proposal_path"].read_text(encoding="utf-8"))
    assert updated_proposal["status"] == "approved"


def test_strategy_proposal_cli_commands(tmp_path: Path):
    propose = runner.invoke(
        app,
        [
            "propose-strategy-change",
            "--date", "2026-04-20",
            "--account", "技术小甜甜",
            "--stage-goal", "提高专栏转化",
            "--target-column", "CSDN专栏增长",
            "--proposed-summary", "增加桥接题比例",
            "--current-summary", "当前以引流题为主",
            "--reason", "最近转化桥接不足",
            "--expected-effect", "增加转化型题目",
            "--risk", "可能影响阅读体验",
            "--source-signal", "sales 周报",
            "--base-dir", str(tmp_path),
        ],
    )
    assert propose.exit_code == 0
    assert "Strategy proposal saved" in propose.output

    proposal_dir = tmp_path / "data" / "business" / "strategy_proposals"
    proposal_files = list(proposal_dir.glob("*.json"))
    assert len(proposal_files) == 1

    approve = runner.invoke(
        app,
        [
            "approve-strategy-change",
            "--proposal-path", str(proposal_files[0]),
            "--base-dir", str(tmp_path),
        ],
    )
    assert approve.exit_code == 0
    assert "Strategy proposal approved" in approve.output
