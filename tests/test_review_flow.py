import json
from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.mvp.review_flow import build_new_main_sample_task, persist_review_package
from app.schemas.execution_result import ExecutionResult
from app.schemas.enums import ExecutionStage, PublishMode, TaskStatus

runner = CliRunner()


def test_build_new_main_sample_task_sets_profile_and_review_defaults():
    task = build_new_main_sample_task()

    assert task.title
    assert task.publish_mode == PublishMode.DRAFT
    assert task.metadata["account_profile"] == "new-main"
    assert task.metadata["requires_human_review"] is True
    assert task.metadata["review_status"] == "pending"



def test_persist_review_package_writes_draft_link_and_manual_action(tmp_path: Path):
    task = build_new_main_sample_task()
    result = ExecutionResult.started(
        task_id="task_123",
        article_id=task.article_id,
        publish_mode=PublishMode.DRAFT,
    )
    result.finish(
        status=TaskStatus.SUCCESS,
        final_stage=ExecutionStage.VERIFY_RESULT,
        draft_url="https://editor.csdn.net/md/?article=123",
    )

    path = persist_review_package(task=task, result=result, output_dir=tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["draft_url"] == "https://editor.csdn.net/md/?article=123"
    assert "手动发布" in payload["review_message"]
    assert payload["account_profile"] == "new-main"



def test_prepare_sample_review_cli_creates_review_package(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "prepare-sample-review",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
