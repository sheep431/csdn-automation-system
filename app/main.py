from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich import print

from app.browser.session_manager import BrowserSessionManager
from app.business.ops import create_topic_brief, build_column_asset, build_baseline_column_assets_from_full_capture, build_baseline_topic_libraries_from_full_capture, build_strategy_output, build_topic_library_dashboard, propose_strategy_change, auto_propose_strategy_change, approve_strategy_change, mark_topic_used, process_topic_batch_feedback, review_business, topic_usage_report, write_topic_batch_files
from app.business.live_topic_batch import plan_topic_batch_from_live
from app.config import (
    DATA_DIR,
    DB_PATH,
    PENDING_TASK_DIR,
    ensure_directories,
    get_browser_profile_dir,
    normalize_profile_name,
)
from app.mvp.review_flow import build_new_main_sample_task, persist_review_package
from app.intel import (
    capture_full_account_content,
    capture_live_account_snapshot,
    collect_intel_record,
    log_competitor_record,
    log_feedback_record,
    log_sales_record,
    refresh_publish_facts_from_account,
    review_intel,
    save_live_account_snapshot,
    sync_topic_usage_from_live_snapshot,
)
from app.ops.new_account_mvp_planner import plan_new_account_daily_mvp
from app.ops.daily_board import create_daily_board
from app.ops.publish_day import prepare_publish_day
from app.process.ops import create_workflow_manifest, materialize_workflow_task, review_process
from app.publishers.csdn_publisher import CSDNPublisher
from app.rules import check_draft_readiness, check_publish_readiness, review_rules, score_topic, write_rule_score_record
from app.runner.execution_runner import ExecutionRunner
from app.state import (
    COLUMN_LIFECYCLE_STATES,
    build_daily_column_allocations_from_slots,
    set_column_lifecycle,
    snapshot_state,
    upsert_state_record,
    write_column_portfolio_review,
    write_daily_column_allocation,
)
from app.execution import execute_topic_pipeline
from app.schemas.article_task import ArticleTask
from app.schemas.enums import ExecutionStage, TaskStatus
from app.schemas.execution_result import ExecutionResult
from app.store.task_store import TaskStore
from app.task_queue.markdown_queue import enqueue_markdown_drafts
from app.task_queue.publish_queue import prepare_publish_task
from app.task_queue.review_gate import is_task_ready_for_execution

app = typer.Typer(help="CSDN automation project CLI")


def build_store() -> TaskStore:
    ensure_directories()
    return TaskStore(DB_PATH)


def load_task_from_file(path: Path) -> ArticleTask:
    data = json.loads(path.read_text(encoding="utf-8"))
    task = ArticleTask(**data)
    task.task_id = f"task_{uuid.uuid4().hex[:12]}"
    return task


def parse_debug_stage(debug_stage: str | None) -> ExecutionStage | None:
    if debug_stage is None:
        return None

    try:
        return ExecutionStage(debug_stage)
    except ValueError as exc:
        allowed = ", ".join(stage.value for stage in ExecutionStage)
        raise typer.BadParameter(f"invalid debug stage: {debug_stage}. allowed: {allowed}") from exc


@app.command()
def init() -> None:
    store = build_store()
    store.init_db()
    print(f"[green]Initialized database:[/green] {DB_PATH}")


@app.command()
def run(
    task: Path = typer.Option(..., "--task", exists=True, readable=True),
    debug_stage: str | None = typer.Option(None, "--debug-stage"),
    profile: str = typer.Option("default", "--profile"),
) -> None:
    store = build_store()
    store.init_db()

    article_task = load_task_from_file(task)
    stage = parse_debug_stage(debug_stage)
    profile_name = normalize_profile_name(profile)

    store.create_task(article_task)

    runner = ExecutionRunner(store, profile_name=profile_name)
    result = asyncio.run(runner.run_task(article_task, debug_stage=stage))

    print("[green]Execution finished[/green]")
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("run-batch")
def run_batch(
    dir_: Path = typer.Option(PENDING_TASK_DIR, "--dir", exists=True, file_okay=False, readable=True),
    profile: str = typer.Option("default", "--profile"),
    approved_only: bool = typer.Option(True, "--approved-only/--all", help="Only run tasks that passed human review"),
) -> None:
    store = build_store()
    store.init_db()

    files = sorted(dir_.glob("*.json"))
    if not files:
        print(f"[yellow]No task files found in[/yellow] {dir_}")
        return

    profile_name = normalize_profile_name(profile)
    runner = ExecutionRunner(store, profile_name=profile_name)

    for file_path in files:
        try:
            article_task = load_task_from_file(file_path)
            if not is_task_ready_for_execution(article_task, approved_only=approved_only):
                print(f"[yellow]Skipped[/yellow] {file_path.name}: waiting for human review approval")
                continue
            store.create_task(article_task)
            result = asyncio.run(runner.run_task(article_task))
            print(
                f"[green]Finished[/green] {file_path.name} -> "
                f"{result.status.value} ({result.final_stage.value})"
            )
        except Exception as exc:
            print(f"[red]Failed[/red] {file_path.name}: {exc}")

    print("[cyan]Batch run finished[/cyan]")


@app.command("enqueue-markdown")
def enqueue_markdown(
    input_path: Path = typer.Option(..., "--input-path", exists=True, readable=True, help="Markdown file or directory to enqueue"),
    output_dir: Path = typer.Option(PENDING_TASK_DIR, "--output-dir", file_okay=False, help="Where to write pending task JSON files"),
    profile: str = typer.Option("default", "--profile", help="Target browser/account profile for these drafts"),
    source: str = typer.Option("generated", "--source", help="Task source label for queued drafts"),
    review_status: str = typer.Option("pending", "--review-status", help="Review gate status: pending/approved/needs_revision"),
    requires_human_review: bool = typer.Option(True, "--requires-human-review/--no-requires-human-review", help="Whether these drafts should be blocked until human approval"),
) -> None:
    ensure_directories()
    profile_name = normalize_profile_name(profile)
    created = enqueue_markdown_drafts(
        input_path=input_path,
        output_dir=output_dir,
        profile=profile_name,
        source=source,
        review_status=review_status,
        requires_human_review=requires_human_review,
    )

    if not created:
        print(f"[yellow]No markdown drafts found in[/yellow] {input_path}")
        raise typer.Exit(code=1)

    print(f"[green]Queued {len(created)} draft task(s)[/green] for profile [cyan]{profile_name}[/cyan]")
    for path in created:
        print(f" - {path}")


@app.command("prepare-publish-task")
def prepare_publish_task_cmd(
    source_task_path: Path = typer.Option(..., "--source-task-path", exists=True, readable=True, help="Existing draft task JSON to promote for publish"),
    output_path: Path = typer.Option(..., "--output-path", help="Where to write the publish-mode task JSON"),
) -> None:
    store = build_store()
    store.init_db()
    result_path = prepare_publish_task(source_task_path=source_task_path, output_path=output_path, store=store)
    print(f"[green]Publish task ready[/green] {result_path}")


@app.command("plan-day")
def plan_day(
    date: str | None = typer.Option(None, "--date", help="Day to plan, format YYYY-MM-DD"),
    output_dir: Path = typer.Option(DATA_DIR / "daily_plans", "--output-dir", file_okay=False, help="Directory for daily board files"),
) -> None:
    board_path = create_daily_board(output_dir=output_dir, board_date=date)
    print(f"[green]Daily board ready[/green] {board_path}")


@app.command("prepare-publish-day")
def prepare_publish_day_cmd(
    plan_json_path: Path = typer.Option(..., "--plan-json-path", exists=True, readable=True, help="JSON plan describing today's publish slots"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Project root; defaults to current automation-system"),
) -> None:
    plan = json.loads(plan_json_path.read_text(encoding="utf-8"))
    result = prepare_publish_day(plan=plan, base_dir=base_dir)
    print(f"[green]Publish-day package ready[/green] {result['manifest_json_path']}")
    print(json.dumps({k: [str(item) for item in v] if isinstance(v, list) else str(v) for k, v in result.items()}, ensure_ascii=False, indent=2))


@app.command("collect-intel")
def collect_intel(
    kind: str = typer.Option(..., "--kind", help="Intel category: accounts/feedback/competitors/market/sales"),
    date: str = typer.Option(..., "--date", help="Record date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Account name related to this record"),
    summary: str = typer.Option(..., "--summary", help="Short summary or observation"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store intel data"),
) -> None:
    path = collect_intel_record(kind=kind, date=date, account=account, summary=summary, base_dir=base_dir)
    print(f"[green]Intel record saved[/green] {path}")


@app.command("log-feedback")
def log_feedback(
    date: str = typer.Option(..., "--date", help="Record date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Account name related to this feedback"),
    source: str = typer.Option(..., "--source", help="Feedback source, e.g. review/comment/message"),
    feedback_type: str = typer.Option(..., "--feedback-type", help="Feedback category, e.g. approved/needs_revision"),
    content: str = typer.Option(..., "--content", help="Feedback content"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store intel data"),
) -> None:
    path = log_feedback_record(
        date=date,
        account=account,
        source=source,
        feedback_type=feedback_type,
        content=content,
        base_dir=base_dir,
    )
    print(f"[green]Feedback record saved[/green] {path}")


@app.command("log-competitor")
def log_competitor(
    date: str = typer.Option(..., "--date", help="Record date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Account name related to this observation"),
    url: str = typer.Option(..., "--url", help="Competitor or example URL"),
    notes: str = typer.Option(..., "--notes", help="Observation notes"),
    tag: str | None = typer.Option(None, "--tag", help="Optional tag"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store intel data"),
) -> None:
    path = log_competitor_record(date=date, account=account, url=url, notes=notes, tag=tag, base_dir=base_dir)
    print(f"[green]Competitor record saved[/green] {path}")


@app.command("log-sales")
def log_sales(
    date: str = typer.Option(..., "--date", help="Record date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Account name related to this record"),
    column: str = typer.Option(..., "--column", help="Column or product name"),
    metric: str = typer.Option(..., "--metric", help="Metric name, e.g. click/paid/order"),
    value: str = typer.Option(..., "--value", help="Metric value"),
    notes: str | None = typer.Option(None, "--notes", help="Optional notes"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store intel data"),
) -> None:
    path = log_sales_record(
        date=date,
        account=account,
        column=column,
        metric=metric,
        value=value,
        notes=notes,
        base_dir=base_dir,
    )
    print(f"[green]Sales record saved[/green] {path}")


@app.command("review-intel")
def review_intel_cmd(
    period: str = typer.Option(..., "--period", help="Review period label: week/month"),
    date: str = typer.Option(..., "--date", help="Review date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Optional account name to scope the review"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store intel data"),
) -> None:
    path = review_intel(period=period, date=date, base_dir=base_dir, account=account)
    print(f"[green]Intel review saved[/green] {path}")


@app.command("import-csdn-live-snapshot")
def import_csdn_live_snapshot_cmd(
    date: str = typer.Option(..., "--date", help="Snapshot date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account label such as 技术小甜甜 / 踏雪无痕老爷子"),
    snapshot_json_path: Path = typer.Option(..., "--snapshot-json-path", exists=True, readable=True, help="Raw live snapshot JSON captured from CSDN pages"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store intel data"),
) -> None:
    snapshot = json.loads(snapshot_json_path.read_text(encoding="utf-8"))
    result = save_live_account_snapshot(date=date, account=account, snapshot=snapshot, base_dir=base_dir)
    print(f"[green]Live CSDN snapshot saved[/green] {result['json_path']}")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("capture-csdn-live")
def capture_csdn_live_cmd(
    date: str = typer.Option(..., "--date", help="Snapshot date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account label such as 技术小甜甜 / 踏雪无痕老爷子"),
    profile: str = typer.Option(..., "--profile", help="Browser profile name, e.g. new-main / old-traffic"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store intel data"),
) -> None:
    result = asyncio.run(capture_live_account_snapshot(date=date, account=account, profile=profile, base_dir=base_dir))
    print(f"[green]Live CSDN snapshot captured[/green] {result['json_path']}")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("sync-published-from-live")
def sync_published_from_live_cmd(
    date: str = typer.Option(..., "--date", help="Sync date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account label such as 技术小甜甜 / 踏雪无痕老爷子"),
    snapshot_path: Path = typer.Option(..., "--snapshot-path", exists=True, readable=True, help="Normalized live snapshot JSON path"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory for business/intel data"),
) -> None:
    result = sync_topic_usage_from_live_snapshot(date=date, account=account, snapshot_path=snapshot_path, base_dir=base_dir)
    print(f"[green]Live publish sync finished[/green] {result['report_path']}")
    print(json.dumps({key: [str(item) for item in value] if isinstance(value, list) else (str(value) if isinstance(value, Path) else value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("refresh-csdn-publish-facts")
def refresh_csdn_publish_facts_cmd(
    date: str = typer.Option(..., "--date", help="Sync date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account label such as 技术小甜甜 / 踏雪无痕老爷子"),
    profile: str = typer.Option(..., "--profile", help="Browser profile name, e.g. new-main / old-traffic"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory for business/intel data"),
) -> None:
    result = asyncio.run(refresh_publish_facts_from_account(date=date, account=account, profile=profile, base_dir=base_dir))
    print(f"[green]Publish facts refreshed from live account[/green] {result['report_path']}")
    print(json.dumps({key: [str(item) for item in value] if isinstance(value, list) else (str(value) if isinstance(value, Path) else value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("capture-csdn-full-account")
def capture_csdn_full_account_cmd(
    date: str = typer.Option(..., "--date", help="Capture date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account label such as 技术小甜甜"),
    profile: str = typer.Option(..., "--profile", help="Browser profile name, e.g. new-main"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory for intel data"),
) -> None:
    result = asyncio.run(capture_full_account_content(date=date, account=account, profile=profile, base_dir=base_dir))
    print(f"[green]Full account capture saved[/green] {result['json_path']}")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("build-strategy-output")
def build_strategy_output_cmd(
    date: str = typer.Option(..., "--date", help="Strategy date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name"),
    stage_goal: str = typer.Option(..., "--stage-goal", help="Current stage goal"),
    target_column: str = typer.Option(..., "--target-column", help="Primary target column for this strategy cycle"),
    strategy_summary: str = typer.Option(..., "--strategy-summary", help="Summary of the current topic strategy"),
    input_item: list[str] = typer.Option([], "--input-item", help="Strategy input evidence; repeatable"),
    adjustment: list[str] = typer.Option([], "--adjustment", help="Adjustments to strengthen or reduce; repeatable"),
    competitor_insight: list[str] = typer.Option([], "--competitor-insight", help="Insights learned from similar columns/competitors; repeatable"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    result = build_strategy_output(
        date=date,
        account=account,
        stage_goal=stage_goal,
        target_column=target_column,
        strategy_summary=strategy_summary,
        inputs=input_item,
        adjustments=adjustment,
        competitor_insights=competitor_insight,
        base_dir=base_dir,
    )
    print("[green]Strategy output saved[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("build-column-asset")
def build_column_asset_cmd(
    date: str = typer.Option(..., "--date", help="Asset date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name"),
    column: str = typer.Option(..., "--column", help="Column name"),
    goal: str = typer.Option(..., "--goal", help="Current goal of this column"),
    existing_topic: list[str] = typer.Option([], "--existing-topic", help="Existing topics already covered in this column; repeatable"),
    gap_topic: list[str] = typer.Option([], "--gap-topic", help="Current gaps to fill; repeatable"),
    topic_role: list[str] = typer.Option([], "--topic-role", help="Desired role mix such as 引流/信任/转化; repeatable"),
    competitor_reference: list[str] = typer.Option([], "--competitor-reference", help="Similar column references; repeatable"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    result = build_column_asset(
        date=date,
        account=account,
        column=column,
        goal=goal,
        existing_topics=existing_topic,
        gap_topics=gap_topic,
        topic_roles=topic_role,
        competitor_references=competitor_reference,
        base_dir=base_dir,
    )
    print("[green]Column asset saved[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("build-column-baseline-from-full")
def build_column_baseline_from_full_cmd(
    date: str = typer.Option(..., "--date", help="Baseline date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name"),
    capture_path: Path = typer.Option(..., "--capture-path", exists=True, readable=True, help="Full account capture JSON path"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    result = build_baseline_column_assets_from_full_capture(
        date=date,
        account=account,
        capture_path=capture_path,
        base_dir=base_dir,
    )
    print("[green]Column baseline assets saved[/green]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("build-topic-library-baseline-from-full")
def build_topic_library_baseline_from_full_cmd(
    date: str = typer.Option(..., "--date", help="Baseline date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name"),
    capture_path: Path = typer.Option(..., "--capture-path", exists=True, readable=True, help="Full account capture JSON path"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    result = build_baseline_topic_libraries_from_full_capture(
        date=date,
        account=account,
        capture_path=capture_path,
        base_dir=base_dir,
    )
    print("[green]Topic library baseline saved[/green]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("build-topic-library-dashboard")
def build_topic_library_dashboard_cmd(
    account: str = typer.Option(..., "--account", help="Account name"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to read business/state data"),
    output_path: Path | None = typer.Option(None, "--output-path", help="Optional explicit dashboard html path"),
) -> None:
    path = build_topic_library_dashboard(account=account, base_dir=base_dir, output_path=output_path)
    print(f"[green]Topic library dashboard saved[/green] {path}")


@app.command("serve-topic-library-dashboard")
def serve_topic_library_dashboard_cmd(
    account: str = typer.Option(..., "--account", help="Account name"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8787, "--port", min=1, max=65535, help="Bind port"),
    profile: str | None = typer.Option(None, "--profile", help="Browser profile for dashboard calibration actions, e.g. new-main / old-traffic"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to read business/state data"),
) -> None:
    project_root = base_dir or DATA_DIR.parent
    resolved_profile = profile or ("new-main" if account == "技术小甜甜" else None)
    action_lock = threading.Lock()
    action_state: dict[str, str] = {}

    def _write_json(handler: BaseHTTPRequestHandler, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status_code)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _run_dashboard_calibration() -> dict[str, object]:
        if not resolved_profile:
            raise ValueError("dashboard calibration requires a browser profile; restart server with --profile")
        date = datetime.utcnow().strftime("%Y-%m-%d")
        capture_result = asyncio.run(
            capture_full_account_content(
                date=date,
                account=account,
                profile=resolved_profile,
                base_dir=base_dir,
            )
        )
        column_result = build_baseline_column_assets_from_full_capture(
            date=date,
            account=account,
            capture_path=capture_result["json_path"],
            base_dir=base_dir,
        )
        library_result = build_baseline_topic_libraries_from_full_capture(
            date=date,
            account=account,
            capture_path=capture_result["json_path"],
            base_dir=base_dir,
        )
        message = f"baseline 校准完成：{date}，更新 {library_result['created_count']} 个题库 / {column_result['created_count']} 个专栏资产"
        action_state["status_message"] = message
        return {
            "ok": True,
            "message": message,
            "date": date,
            "capture_path": str(capture_result["json_path"]),
            "library_count": library_result["created_count"],
            "column_count": column_result["created_count"],
        }

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if parsed.path not in {"/", "/index.html"}:
                body = b"not found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            output_path = project_root / "docs" / "specs" / "topic-library-dashboard.live.html"
            build_topic_library_dashboard(
                account=account,
                base_dir=base_dir,
                output_path=output_path,
                action_config={
                    "calibrate_path": "/actions/calibrate",
                    "can_calibrate": bool(resolved_profile),
                    "calibrate_label": "校准 baseline",
                    "disabled_reason": "当前服务未配置 profile，无法从页面直接校准 baseline" if not resolved_profile else "",
                    "status_message": action_state.get("status_message", ""),
                },
            )
            body = output_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/actions/calibrate":
                _write_json(self, 404, {"ok": False, "error": "not found"})
                return
            if not resolved_profile:
                _write_json(self, 400, {"ok": False, "error": "dashboard calibration requires --profile"})
                return
            if not action_lock.acquire(blocking=False):
                _write_json(self, 409, {"ok": False, "error": "calibration already running"})
                return
            try:
                payload = _run_dashboard_calibration()
            except Exception as exc:
                action_state["status_message"] = f"baseline 校准失败：{exc}"
                _write_json(self, 500, {"ok": False, "error": str(exc)})
            else:
                _write_json(self, 200, payload)
            finally:
                action_lock.release()

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), DashboardHandler)
    url = f"http://{host}:{port}"
    print(f"[green]Topic library dashboard server running[/green] {url}")
    print(f"[cyan]Refresh this URL any time to read the latest topic-library state.[/cyan]")
    if resolved_profile:
        print(f"[cyan]Dashboard calibration profile:[/cyan] {resolved_profile}")
    else:
        print("[yellow]Dashboard calibration button will be disabled until you restart with --profile.[/yellow]")
    print("[cyan]Health check:[/cyan] " + url + "/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[yellow]Dashboard server stopped[/yellow]")
    finally:
        server.server_close()


@app.command("propose-strategy-change")
def propose_strategy_change_cmd(
    date: str = typer.Option(..., "--date", help="Proposal date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name"),
    stage_goal: str = typer.Option(..., "--stage-goal", help="Current stage goal"),
    target_column: str = typer.Option(..., "--target-column", help="Primary target column"),
    proposed_summary: str = typer.Option(..., "--proposed-summary", help="Proposed new strategy summary"),
    current_summary: str | None = typer.Option(None, "--current-summary", help="Current official strategy summary, if any"),
    reason: list[str] = typer.Option([], "--reason", help="Why this strategy change is suggested; repeatable"),
    expected_effect: list[str] = typer.Option([], "--expected-effect", help="Expected topic/publish impact; repeatable"),
    risk: list[str] = typer.Option([], "--risk", help="Risks or cautions; repeatable"),
    source_signal: list[str] = typer.Option([], "--source-signal", help="Source signals from intel/feedback/competitors; repeatable"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    result = propose_strategy_change(
        date=date,
        account=account,
        stage_goal=stage_goal,
        target_column=target_column,
        current_summary=current_summary,
        proposed_summary=proposed_summary,
        reasons=reason,
        expected_effects=expected_effect,
        risks=risk,
        source_signals=source_signal,
        base_dir=base_dir,
    )
    print("[green]Strategy proposal saved[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("auto-propose-strategy-change")
def auto_propose_strategy_change_cmd(
    date: str = typer.Option(..., "--date", help="Proposal date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name"),
    stage_goal: str = typer.Option(..., "--stage-goal", help="Current stage goal"),
    target_column: str = typer.Option(..., "--target-column", help="Primary target column"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to read and write business/intel data"),
) -> None:
    result = auto_propose_strategy_change(
        date=date,
        account=account,
        stage_goal=stage_goal,
        target_column=target_column,
        base_dir=base_dir,
    )
    print("[green]Auto strategy proposal saved[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("approve-strategy-change")
def approve_strategy_change_cmd(
    proposal_path: Path = typer.Option(..., "--proposal-path", exists=True, readable=True, help="Pending strategy proposal JSON file"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    result = approve_strategy_change(proposal_path=proposal_path, base_dir=base_dir)
    print("[green]Strategy proposal approved[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("plan-topic")
def plan_topic(
    date: str = typer.Option(..., "--date", help="Decision date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name, e.g. 技术小甜甜"),
    title: str = typer.Option(..., "--title", help="Topic or article title"),
    audience: str = typer.Option(..., "--audience", help="Target reader description"),
    column: str = typer.Option(..., "--column", help="Column or series this topic belongs to"),
    angle: str = typer.Option(..., "--angle", help="How this topic should be approached"),
    value: str = typer.Option(..., "--value", help="Why this topic is worth writing"),
    cta: str = typer.Option(..., "--cta", help="Call to action or conversion path"),
    why_now: str | None = typer.Option(None, "--why-now", help="Why it should be written now"),
    source_input: list[str] = typer.Option([], "--source-input", help="Reference inputs or intel notes; can be repeated"),
    strategy_path: Path | None = typer.Option(None, "--strategy-path", exists=True, readable=True, help="Optional strategy output file path"),
    column_asset_path: Path | None = typer.Option(None, "--column-asset-path", exists=True, readable=True, help="Optional column asset file path"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    path = create_topic_brief(
        date=date,
        account=account,
        title=title,
        audience=audience,
        column=column,
        angle=angle,
        value=value,
        cta=cta,
        source_inputs=source_input,
        why_now=why_now,
        strategy_path=strategy_path,
        column_asset_path=column_asset_path,
        base_dir=base_dir,
    )
    print(f"[green]Business topic brief saved[/green] {path}")


@app.command("review-business")
def review_business_cmd(
    date: str = typer.Option(..., "--date", help="Review date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Optional account name to scope the review"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store business data"),
) -> None:
    path = review_business(date=date, base_dir=base_dir, account=account)
    print(f"[green]Business review saved[/green] {path}")


@app.command("apply-topic-feedback")
def apply_topic_feedback_cmd(
    date: str = typer.Option(..., "--date", help="Feedback date, format YYYY-MM-DD"),
    batch_path: Path = typer.Option(..., "--batch-path", exists=True, readable=True, help="Original topic batch JSON file"),
    feedback: str = typer.Option(..., "--feedback", help="Natural-language feedback from the user"),
    account: str | None = typer.Option(None, "--account", help="Optional account override"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store feedback learning data"),
) -> None:
    result = process_topic_batch_feedback(
        date=date,
        batch_path=batch_path,
        feedback=feedback,
        account=account,
        base_dir=base_dir,
    )
    print("[green]Topic feedback applied[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("save-topic-batch")
def save_topic_batch_cmd(
    date: str = typer.Option(..., "--date", help="Batch date, format YYYY-MM-DD"),
    batch_json_path: Path = typer.Option(..., "--batch-json-path", exists=True, readable=True, help="Structured topic batch JSON file to validate and save"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store topic batch files"),
) -> None:
    payload = json.loads(batch_json_path.read_text(encoding="utf-8"))
    result = write_topic_batch_files(batch=payload, date=date, base_dir=base_dir)
    print("[green]Topic batch saved[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("plan-topic-batch-from-live")
def plan_topic_batch_from_live_cmd(
    date: str = typer.Option(..., "--date", help="Batch date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account label such as 技术小甜甜 / 踏雪无痕老爷子"),
    snapshot_path: Path = typer.Option(..., "--snapshot-path", exists=True, readable=True, help="Normalized same-day live snapshot JSON path"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store topic batch files"),
) -> None:
    result = plan_topic_batch_from_live(date=date, account=account, snapshot_path=snapshot_path, base_dir=base_dir)
    print(f"[green]Live topic batch saved[/green] {result['json_path']}")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("mark-topic-used")
def mark_topic_used_cmd(
    date: str = typer.Option(..., "--date", help="Usage date, format YYYY-MM-DD"),
    batch_path: Path = typer.Option(..., "--batch-path", exists=True, readable=True, help="Topic batch JSON file"),
    topic_number: int = typer.Option(..., "--topic-number", min=1, help="Topic number inside the batch"),
    status: str = typer.Option("used", "--status", help="Usage status: approved/used/published/rejected/archived"),
    account: str | None = typer.Option(None, "--account", help="Optional account override"),
    notes: str | None = typer.Option(None, "--notes", help="Optional usage note"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store topic usage ledger"),
) -> None:
    result = mark_topic_used(
        date=date,
        batch_path=batch_path,
        topic_number=topic_number,
        status=status,
        account=account,
        notes=notes,
        base_dir=base_dir,
    )
    print("[green]Topic usage recorded[/green]")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("topic-usage-report")
def topic_usage_report_cmd(
    date: str = typer.Option(..., "--date", help="Report date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Optional account filter"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to read topic usage ledger"),
) -> None:
    path = topic_usage_report(date=date, account=account, base_dir=base_dir)
    print(f"[green]Topic usage report saved[/green] {path}")


@app.command("plan-workflow")
def plan_workflow(
    date: str = typer.Option(..., "--date", help="Workflow date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name, e.g. 技术小甜甜"),
    title: str = typer.Option(..., "--title", help="Article title"),
    body_markdown: str = typer.Option(..., "--body-markdown", help="Article body markdown"),
    column: str = typer.Option(..., "--column", help="Column or series name"),
    tag: list[str] = typer.Option([], "--tag", help="Article tag; can be repeated"),
    source_brief_path: Path | None = typer.Option(None, "--source-brief-path", help="Optional business brief path"),
    why_now: str | None = typer.Option(None, "--why-now", help="Why this workflow should run now"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory for process data"),
) -> None:
    flow_path = create_workflow_manifest(
        date=date,
        account=account,
        title=title,
        column=column,
        body_markdown=body_markdown,
        tags=tag,
        source_brief_path=source_brief_path,
        why_now=why_now,
        base_dir=base_dir,
    )
    task_path = materialize_workflow_task(
        date=date,
        account=account,
        title=title,
        body_markdown=body_markdown,
        tags=tag,
        column=column,
        source_brief_path=source_brief_path,
        why_now=why_now,
        base_dir=base_dir,
    )
    print(f"[green]Workflow flow saved[/green] {flow_path}")
    print(f"[green]Workflow task saved[/green] {task_path}")


@app.command("review-process")
def review_process_cmd(
    date: str = typer.Option(..., "--date", help="Review date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Optional account name to scope the review"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store process data"),
) -> None:
    path = review_process(date=date, base_dir=base_dir, account=account)
    print(f"[green]Process review saved[/green] {path}")


@app.command("score-topic")
def score_topic_cmd(
    date: str = typer.Option(..., "--date", help="Assessment date, format YYYY-MM-DD"),
    title: str = typer.Option(..., "--title", help="Topic title"),
    account: str | None = typer.Option(None, "--account", help="Optional account name"),
    value_score: int = typer.Option(..., "--value-score", min=1, max=5),
    relevance_score: int = typer.Option(..., "--relevance-score", min=1, max=5),
    cost_score: int = typer.Option(..., "--cost-score", min=1, max=5, help="Higher means easier to write"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store rule assessments"),
) -> None:
    path = write_rule_score_record(
        date=date,
        title=title,
        account=account,
        value_score=value_score,
        relevance_score=relevance_score,
        cost_score=cost_score,
        base_dir=base_dir,
    )
    evaluation = score_topic(value_score=value_score, relevance_score=relevance_score, cost_score=cost_score)
    print(f"[green]Rule score saved[/green] {path}")
    print(json.dumps(evaluation, ensure_ascii=False, indent=2))


@app.command("check-draft")
def check_draft_cmd(
    title: str = typer.Option(..., "--title", help="Draft title"),
    body_markdown: str = typer.Option(..., "--body-markdown", help="Draft body markdown"),
) -> None:
    result = check_draft_readiness(title=title, body_markdown=body_markdown)
    print(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("check-publish")
def check_publish_cmd(
    draft_exists: bool = typer.Option(..., "--draft-exists/--no-draft-exists"),
    review_status: str = typer.Option(..., "--review-status"),
    draft_url: str | None = typer.Option(None, "--draft-url"),
    owner: str | None = typer.Option(None, "--owner"),
) -> None:
    result = check_publish_readiness(
        draft_exists=draft_exists,
        review_status=review_status,
        draft_url=draft_url,
        owner=owner,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("review-rules")
def review_rules_cmd(
    date: str = typer.Option(..., "--date", help="Review date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Optional account name to scope the review"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store rule data"),
) -> None:
    path = review_rules(date=date, base_dir=base_dir, account=account)
    print(f"[green]Rules review saved[/green] {path}")


@app.command("record-state")
def record_state(
    object_type: str = typer.Option(..., "--object-type", help="State object type: account/topic/draft/review_package/publish_task/feedback/daily_plan/column/column_allocation"),
    object_id: str = typer.Option(..., "--object-id", help="Stable object id"),
    state: str = typer.Option(..., "--state", help="Current state value"),
    notes: str | None = typer.Option(None, "--notes", help="Optional notes"),
    source_path: str | None = typer.Option(None, "--source-path", help="Optional source file path"),
    attribute: list[str] = typer.Option([], "--attribute", help="Key=value metadata, repeatable"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store state data"),
) -> None:
    attributes: dict[str, str] = {}
    for item in attribute:
        if "=" not in item:
            raise typer.BadParameter("attribute must be key=value")
        key, value = item.split("=", 1)
        attributes[key.strip()] = value.strip()

    path = upsert_state_record(
        object_type=object_type,
        object_id=object_id,
        state=state,
        notes=notes,
        source_path=source_path,
        attributes=attributes,
        base_dir=base_dir,
    )
    print(f"[green]State record saved[/green] {path}")


@app.command("state-snapshot")
def state_snapshot_cmd(
    date: str = typer.Option(..., "--date", help="Snapshot date, format YYYY-MM-DD"),
    account: str | None = typer.Option(None, "--account", help="Optional account name to scope the snapshot"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store state data"),
) -> None:
    path = snapshot_state(date=date, base_dir=base_dir, account=account)
    print(f"[green]State snapshot saved[/green] {path}")


@app.command("set-column-lifecycle")
def set_column_lifecycle_cmd(
    date: str = typer.Option(..., "--date", help="Record date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name, e.g. 技术小甜甜"),
    column: str = typer.Option(..., "--column", help="Column name"),
    lifecycle_state: str = typer.Option(..., "--lifecycle-state", help=f"One of: {', '.join(COLUMN_LIFECYCLE_STATES)}"),
    role: str | None = typer.Option(None, "--role", help="Optional role such as flagship_revenue / secondary_revenue / traffic"),
    notes: str | None = typer.Option(None, "--notes", help="Optional notes"),
    source_path: str | None = typer.Option(None, "--source-path", help="Optional source artifact path"),
    attribute: list[str] = typer.Option([], "--attribute", help="Key=value metadata, repeatable"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store state data"),
) -> None:
    attributes: dict[str, str] = {}
    for item in attribute:
        if "=" not in item:
            raise typer.BadParameter("attribute must be key=value")
        key, value = item.split("=", 1)
        attributes[key.strip()] = value.strip()
    path = set_column_lifecycle(
        date=date,
        account=account,
        column=column,
        lifecycle_state=lifecycle_state,
        role=role,
        notes=notes,
        source_path=source_path,
        attributes=attributes,
        base_dir=base_dir,
    )
    print(f"[green]Column lifecycle saved[/green] {path}")


@app.command("write-daily-column-allocation")
def write_daily_column_allocation_cmd(
    date: str = typer.Option(..., "--date", help="Allocation date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name, e.g. 技术小甜甜"),
    slot: list[str] = typer.Option([], "--slot", help="slot_index|column|role|lifecycle_state|rationale|score|signal1;signal2"),
    notes: str | None = typer.Option(None, "--notes", help="Optional notes"),
    source_signal: list[str] = typer.Option([], "--source-signal", help="Global source signal; repeatable"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store allocation artifacts"),
) -> None:
    allocations: list[dict[str, object]] = []
    for item in slot:
        parts = item.split("|", 6)
        if len(parts) < 5:
            raise typer.BadParameter("slot must be slot_index|column|role|lifecycle_state|rationale|score|signal1;signal2")
        slot_index_text, column, role, lifecycle_state, rationale = parts[:5]
        score = None
        signals: list[str] = []
        if len(parts) >= 6 and parts[5].strip():
            score = float(parts[5].strip())
        if len(parts) == 7 and parts[6].strip():
            signals = [piece.strip() for piece in parts[6].split(";") if piece.strip()]
        allocations.append(
            {
                "slot_index": int(slot_index_text),
                "column": column.strip(),
                "role": role.strip(),
                "lifecycle_state": lifecycle_state.strip(),
                "rationale": rationale.strip(),
                "score": score,
                "source_signals": signals,
            }
        )
    result = write_daily_column_allocation(
        date=date,
        account=account,
        allocations=allocations,
        notes=notes,
        source_signals=source_signal,
        base_dir=base_dir,
    )
    print(f"[green]Daily column allocation saved[/green] {result['json_path']}")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("column-portfolio-review")
def column_portfolio_review_cmd(
    date: str = typer.Option(..., "--date", help="Review date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name, e.g. 技术小甜甜"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory to store portfolio review artifacts"),
) -> None:
    result = write_column_portfolio_review(date=date, account=account, base_dir=base_dir)
    print(f"[green]Column portfolio review saved[/green] {result['json_path']}")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command("execute-topic")
def execute_topic_cmd(
    date: str = typer.Option(..., "--date", help="Execution date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account name, e.g. 技术小甜甜"),
    title: str = typer.Option(..., "--title", help="Article title"),
    audience: str = typer.Option(..., "--audience", help="Target reader description"),
    column: str = typer.Option(..., "--column", help="Column or series name"),
    angle: str = typer.Option(..., "--angle", help="How this topic should be approached"),
    value: str = typer.Option(..., "--value", help="Why this topic is worth writing"),
    cta: str = typer.Option(..., "--cta", help="Call to action or conversion path"),
    body_markdown: str = typer.Option(..., "--body-markdown", help="Article body markdown"),
    tag: list[str] = typer.Option([], "--tag", help="Article tag; can be repeated"),
    why_now: str | None = typer.Option(None, "--why-now", help="Why this workflow should run now"),
    source_input: list[str] = typer.Option([], "--source-input", help="Reference inputs or intel notes; can be repeated"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory for execution artifacts"),
) -> None:
    result = execute_topic_pipeline(
        date=date,
        account=account,
        title=title,
        audience=audience,
        column=column,
        angle=angle,
        value=value,
        cta=cta,
        body_markdown=body_markdown,
        tags=tag,
        why_now=why_now,
        source_inputs=source_input,
        base_dir=base_dir,
    )
    print(f"[green]Execution finished[/green] {result['workflow_task_path']}")
    print(json.dumps({k: str(v) if isinstance(v, Path) else v for k, v in result.items()}, ensure_ascii=False, indent=2))


@app.command("prepare-sample-review")
def prepare_sample_review(
    output_dir: Path = typer.Option(DATA_DIR / "review_packages", "--output-dir", file_okay=False),
) -> None:
    task = build_new_main_sample_task()
    result = ExecutionResult.started(
        task_id="sample-review",
        article_id=task.article_id,
        publish_mode=task.publish_mode,
    )
    result.finish(
        status=TaskStatus.SUCCESS,
        final_stage=ExecutionStage.VERIFY_RESULT,
        draft_url="https://editor.csdn.net/md/",
    )
    package_path = persist_review_package(task=task, result=result, output_dir=output_dir)
    print(f"[green]Sample review package ready[/green] {package_path}")


@app.command("plan-new-account-daily-mvp")
def plan_new_account_daily_mvp_cmd(
    date: str = typer.Option(..., "--date", help="Plan date, format YYYY-MM-DD"),
    account: str = typer.Option(..., "--account", help="Account label such as 技术小甜甜"),
    capture_path: Path = typer.Option(..., "--capture-path", exists=True, readable=True, help="Full account capture JSON path"),
    base_dir: Path | None = typer.Option(None, "--base-dir", file_okay=False, help="Root directory for daily plan output"),
) -> None:
    result = plan_new_account_daily_mvp(date=date, account=account, capture_path=capture_path, base_dir=base_dir)
    print(f"[green]New-account daily MVP plan saved[/green] {result['json_path']}")
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


@app.command()
def status(article_id: str = typer.Option(..., "--article-id")) -> None:
    store = build_store()
    store.init_db()

    idempotency = store.get_idempotency_record(article_id)
    latest_result = store.get_latest_result(article_id)

    output = {
        "article_id": article_id,
        "idempotency_record": idempotency,
        "latest_result": latest_result,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


@app.command("switch-account")
def switch_account(
    profile: str = typer.Option(..., "--profile", help="Name of the browser profile to create/update"),
    hold_seconds: int = typer.Option(600, "--hold-seconds", min=30, help="How long to keep the browser open for manual login"),
) -> None:
    ensure_directories()
    profile_name = normalize_profile_name(profile)
    profile_dir = get_browser_profile_dir(profile_name)

    print(f"[cyan]Opening CSDN editor for profile:[/cyan] {profile_name}")
    print(f"[cyan]Profile dir:[/cyan] {profile_dir}")

    async def _run() -> None:
        session = BrowserSessionManager(profile_name=profile_name)
        page = await session.new_page()
        publisher = CSDNPublisher(page)

        try:
            await publisher.open_editor()
            print("[yellow]Please switch/login to the desired CSDN account in the opened browser window.[/yellow]")
            print(f"[yellow]Browser will remain open for {hold_seconds} seconds.[/yellow]")
            await asyncio.sleep(hold_seconds)
        finally:
            await session.close()

    asyncio.run(_run())
    print(f"[green]Profile saved:[/green] {profile_name}")


if __name__ == "__main__":
    app()
