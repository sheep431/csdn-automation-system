from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from app.business.ops import create_topic_brief
from app.process.ops import create_workflow_manifest, materialize_workflow_task
from app.state.ops import snapshot_state, upsert_state_record


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "untitled"


def _read_task_payload(task_path: Path) -> dict:
    return json.loads(task_path.read_text(encoding="utf-8"))


def execute_topic_pipeline(
    *,
    date: str,
    account: str,
    title: str,
    audience: str,
    column: str,
    angle: str,
    value: str,
    cta: str,
    body_markdown: str,
    tags: list[str],
    why_now: str | None,
    source_inputs: list[str] | None,
    base_dir: Path | None,
) -> dict[str, object]:
    business_brief_path = create_topic_brief(
        date=date,
        account=account,
        title=title,
        audience=audience,
        column=column,
        angle=angle,
        value=value,
        cta=cta,
        source_inputs=source_inputs,
        why_now=why_now,
        base_dir=base_dir,
    )

    workflow_flow_path = create_workflow_manifest(
        date=date,
        account=account,
        title=title,
        column=column,
        body_markdown=body_markdown,
        tags=tags,
        source_brief_path=business_brief_path,
        why_now=why_now,
        base_dir=base_dir,
    )

    workflow_task_path = materialize_workflow_task(
        date=date,
        account=account,
        title=title,
        body_markdown=body_markdown,
        tags=tags,
        column=column,
        source_brief_path=business_brief_path,
        why_now=why_now,
        base_dir=base_dir,
    )

    task_payload = _read_task_payload(workflow_task_path)
    article_id = str(task_payload["article_id"])
    topic_id = f"topic-{date}-{_slugify(title)[:32]}"
    draft_id = article_id
    review_package_id = f"review-{draft_id}"

    topic_state_path = upsert_state_record(
        object_type="topic",
        object_id=topic_id,
        state="selected",
        notes=why_now,
        source_path=str(business_brief_path),
        attributes={
            "account": account,
            "title": title,
            "column": column,
            "audience": audience,
        },
        base_dir=base_dir,
    )

    draft_state_path = upsert_state_record(
        object_type="draft",
        object_id=draft_id,
        state="waiting_review",
        notes="流程层已生成待审任务",
        source_path=str(workflow_task_path),
        attributes={
            "account": account,
            "title": title,
            "topic_id": topic_id,
            "workflow_stage": "waiting_review",
        },
        base_dir=base_dir,
    )

    review_package_path = upsert_state_record(
        object_type="review_package",
        object_id=review_package_id,
        state="created",
        notes="执行层已生成待审信息",
        source_path=str(workflow_flow_path),
        attributes={
            "account": account,
            "draft_id": draft_id,
            "topic_id": topic_id,
        },
        base_dir=base_dir,
    )

    snapshot_path = snapshot_state(date=date, base_dir=base_dir, account=account)

    return {
        "business_brief_path": business_brief_path,
        "workflow_flow_path": workflow_flow_path,
        "workflow_task_path": workflow_task_path,
        "topic_state_path": topic_state_path,
        "draft_state_path": draft_state_path,
        "review_package_path": review_package_path,
        "state_snapshot_path": snapshot_path,
        "topic_id": topic_id,
        "draft_id": draft_id,
        "review_package_id": review_package_id,
        "executed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
