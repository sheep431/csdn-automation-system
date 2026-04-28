import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.ops.daily_board import create_daily_board

runner = CliRunner()


def test_create_daily_board_builds_two_slots_per_account(tmp_path: Path):
    board_path = create_daily_board(output_dir=tmp_path, board_date="2026-04-19")

    payload = json.loads(board_path.read_text(encoding="utf-8"))
    assert payload["date"] == "2026-04-19"
    assert payload["slot_count"] == 4
    assert len(payload["slots"]) == 4

    profiles = [slot["account_profile"] for slot in payload["slots"]]
    assert profiles.count("old-traffic") == 2
    assert profiles.count("new-main") == 2
    assert payload["slots"][0]["goal"] == "traffic"
    assert payload["slots"][2]["goal"] == "revenue"
    assert payload["slots"][0]["status"] == "topic_pending"



def test_plan_day_cli_writes_daily_board_file(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "plan-day",
            "--date",
            "2026-04-19",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    board_file = tmp_path / "2026-04-19.json"
    assert board_file.exists()
    payload = json.loads(board_file.read_text(encoding="utf-8"))
    assert payload["date"] == "2026-04-19"
