from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import DATA_DIR

STATE_OBJECT_TYPES = (
    "account",
    "topic",
    "draft",
    "review_package",
    "publish_task",
    "feedback",
    "daily_plan",
    "column",
    "column_allocation",
)

COLUMN_LIFECYCLE_STATES = (
    "active_revenue",
    "active_traffic",
    "incubating",
    "paused",
    "deprecated",
)


def resolve_state_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "state"
    return base_dir / "data" / "state"


def ensure_state_directories(base_dir: Path | None) -> Path:
    root = resolve_state_root(base_dir)
    (root / "ledger").mkdir(parents=True, exist_ok=True)
    (root / "history").mkdir(parents=True, exist_ok=True)
    (root / "snapshots").mkdir(parents=True, exist_ok=True)
    for object_type in STATE_OBJECT_TYPES:
        (root / "ledger" / object_type).mkdir(parents=True, exist_ok=True)
        (root / "history" / object_type).mkdir(parents=True, exist_ok=True)
    return root


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _state_file(root: Path, object_type: str, object_id: str) -> Path:
    return root / "ledger" / object_type / f"{object_id}.json"


def _history_file(root: Path, object_type: str, object_id: str) -> Path:
    return root / "history" / object_type / f"{object_id}.jsonl"


def _slugify(value: str) -> str:
    cleaned = []
    for ch in value.strip().lower():
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            cleaned.append(ch)
        else:
            cleaned.append("-")
    result = "".join(cleaned).strip("-")
    while "--" in result:
        result = result.replace("--", "-")
    return result or "untitled"


def _column_allocations_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "business" / "column_allocations"
    return base_dir / "data" / "business" / "column_allocations"


def _column_portfolio_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "business" / "column_portfolio"
    return base_dir / "data" / "business" / "column_portfolio"


def upsert_state_record(
    *,
    object_type: str,
    object_id: str,
    state: str,
    base_dir: Path | None,
    notes: str | None = None,
    source_path: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Path:
    root = ensure_state_directories(base_dir)
    latest_path = _state_file(root, object_type, object_id)
    history_path = _history_file(root, object_type, object_id)
    now = _utc_now_iso()

    previous: dict[str, Any] | None = None
    if latest_path.exists():
        try:
            previous = json.loads(latest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None

    created_at = previous.get("created_at", now) if previous else now
    history_count = int(previous.get("history_count", 0)) + 1 if previous else 1

    record: dict[str, Any] = {
        "object_type": object_type,
        "object_id": object_id,
        "state": state,
        "notes": notes,
        "source_path": source_path,
        "attributes": attributes or {},
        "created_at": created_at,
        "updated_at": now,
        "history_count": history_count,
    }
    latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    history_entry = {
        "object_type": object_type,
        "object_id": object_id,
        "state": state,
        "notes": notes,
        "source_path": source_path,
        "attributes": attributes or {},
        "timestamp": now,
    }
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(history_entry, ensure_ascii=False) + "\n")

    return latest_path


def set_column_lifecycle(
    *,
    date: str,
    account: str,
    column: str,
    lifecycle_state: str,
    base_dir: Path | None,
    role: str | None = None,
    notes: str | None = None,
    source_path: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Path:
    if lifecycle_state not in COLUMN_LIFECYCLE_STATES:
        raise ValueError(f"unsupported column lifecycle state: {lifecycle_state}")
    merged_attributes = dict(attributes or {})
    merged_attributes.update(
        {
            "date": date,
            "account": account,
            "column": column,
        }
    )
    if role:
        merged_attributes["role"] = role
    object_id = f"{_slugify(account)}__{_slugify(column)}"
    return upsert_state_record(
        object_type="column",
        object_id=object_id,
        state=lifecycle_state,
        notes=notes,
        source_path=source_path,
        attributes=merged_attributes,
        base_dir=base_dir,
    )


def write_daily_column_allocation(
    *,
    date: str,
    account: str,
    allocations: list[dict[str, Any]],
    base_dir: Path | None,
    notes: str | None = None,
    source_signals: list[str] | None = None,
) -> dict[str, Path]:
    if not allocations:
        raise ValueError("allocations must be non-empty")
    root = _column_allocations_root(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    stem = f"daily-column-allocation_{date}_{_slugify(account)}"
    json_path = root / f"{stem}.json"
    md_path = root / f"{stem}.md"

    normalized_allocations: list[dict[str, Any]] = []
    for index, item in enumerate(allocations, start=1):
        column = str(item.get("column") or "").strip()
        role = str(item.get("role") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        lifecycle_state = str(item.get("lifecycle_state") or "active_revenue").strip()
        if not column or not role or not rationale:
            raise ValueError(f"allocation #{index} missing required fields")
        normalized_allocations.append(
            {
                "slot_index": int(item.get("slot_index") or index),
                "column": column,
                "role": role,
                "lifecycle_state": lifecycle_state,
                "score": item.get("score"),
                "rationale": rationale,
                "source_signals": list(item.get("source_signals") or []),
            }
        )

    payload = {
        "date": date,
        "account": account,
        "allocation_count": len(normalized_allocations),
        "allocations": normalized_allocations,
        "notes": notes or "",
        "source_signals": source_signals or [],
        "generated_at": _utc_now_iso(),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 当日专栏分配",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 分配数: {len(normalized_allocations)}",
    ]
    if notes:
        lines.append(f"- 说明: {notes}")
    lines.append("")
    for item in normalized_allocations:
        lines.extend(
            [
                f"## 槽位 {item['slot_index']} - {item['column']}",
                f"- 角色: {item['role']}",
                f"- 生命周期状态: {item['lifecycle_state']}",
                f"- 分数: {item['score']}",
                f"- 原因: {item['rationale']}",
            ]
        )
        for signal in item["source_signals"]:
            lines.append(f"- 信号: {signal}")
        lines.append("")
    if source_signals:
        lines.append("## 全局信号")
        for signal in source_signals:
            lines.append(f"- {signal}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    allocation_object_id = f"{date}__{_slugify(account)}"
    state_path = upsert_state_record(
        object_type="column_allocation",
        object_id=allocation_object_id,
        state="planned",
        notes=notes or "daily column allocation generated",
        source_path=str(json_path),
        attributes={
            "date": date,
            "account": account,
            "allocation_count": len(normalized_allocations),
            "columns": [item["column"] for item in normalized_allocations],
        },
        base_dir=base_dir,
    )
    return {"json_path": json_path, "md_path": md_path, "state_path": state_path}


def read_state_record(
    *,
    object_type: str,
    object_id: str,
    base_dir: Path | None,
) -> dict[str, Any] | None:
    root = ensure_state_directories(base_dir)
    latest_path = _state_file(root, object_type, object_id)
    if not latest_path.exists():
        return None
    return json.loads(latest_path.read_text(encoding="utf-8"))


def get_column_lifecycle(*, account: str, column: str, base_dir: Path | None) -> dict[str, Any] | None:
    object_id = f"{_slugify(account)}__{_slugify(column)}"
    return read_state_record(object_type="column", object_id=object_id, base_dir=base_dir)


def infer_column_role_and_state(column: str) -> tuple[str, str]:
    if "Dify" in column or "企业级AI落地" in column or "应用系统" in column:
        return "revenue", "active_revenue"
    if "每日速读" in column or "前沿" in column:
        return "traffic", "active_traffic"
    return "mixed", "incubating"


def build_daily_column_allocations_from_slots(
    *,
    date: str,
    account: str,
    slots: list[dict[str, Any]],
    base_dir: Path | None,
    notes: str | None = None,
    source_signals: list[str] | None = None,
) -> dict[str, Path]:
    allocations: list[dict[str, Any]] = []
    for index, slot in enumerate(slots, start=1):
        column = str(slot.get("column") or slot.get("strategy") or "").strip()
        if not column:
            raise ValueError(f"slot #{index} missing column/strategy")
        lifecycle = get_column_lifecycle(account=account, column=column, base_dir=base_dir)
        if lifecycle:
            lifecycle_state = str(lifecycle.get("state") or "incubating")
            role = str((lifecycle.get("attributes") or {}).get("role") or "managed_column")
        else:
            inferred_role, inferred_state = infer_column_role_and_state(column)
            lifecycle_state = inferred_state
            if index == 1 and inferred_role == "revenue":
                role = "flagship_revenue"
            elif inferred_role == "traffic":
                role = "traffic_support"
            elif inferred_role == "revenue":
                role = "secondary_revenue"
            else:
                role = "incubating_column"
        rationale = str(slot.get("allocation_rationale") or slot.get("why_now") or slot.get("notes") or f"根据当日槽位为 {column} 分配发布任务").strip()
        allocations.append(
            {
                "slot_index": int(slot.get("slot_index") or index),
                "column": column,
                "role": role,
                "lifecycle_state": lifecycle_state,
                "score": slot.get("column_score"),
                "rationale": rationale,
                "source_signals": list(slot.get("column_source_signals") or []),
            }
        )
    return write_daily_column_allocation(
        date=date,
        account=account,
        allocations=allocations,
        notes=notes,
        source_signals=source_signals,
        base_dir=base_dir,
    )


def _latest_files(path: Path, limit: int = 10) -> list[Path]:
    if not path.exists():
        return []
    files = [item for item in path.iterdir() if item.is_file()]
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[:limit]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_column_portfolio_review(*, date: str, account: str, base_dir: Path | None) -> dict[str, Path]:
    root = ensure_state_directories(base_dir)
    portfolio_root = _column_portfolio_root(base_dir)
    portfolio_root.mkdir(parents=True, exist_ok=True)
    stem = f"column-portfolio-review_{date}_{_slugify(account)}"
    json_path = portfolio_root / f"{stem}.json"
    md_path = portfolio_root / f"{stem}.md"

    column_records: list[dict[str, Any]] = []
    for file_path in sorted((root / "ledger" / "column").glob("*.json")):
        try:
            record = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        attrs = record.get("attributes") or {}
        if str(attrs.get("account") or "").strip() != account:
            continue
        column_records.append(record)

    allocation_files = _latest_files(_column_allocations_root(base_dir), limit=20)
    relevant_allocations: list[dict[str, Any]] = []
    for path in allocation_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if str(payload.get("account") or "").strip() != account:
            continue
        relevant_allocations.append(payload)

    business_root = (base_dir / "data" / "business") if base_dir else DATA_DIR / "business"
    intel_root = (base_dir / "data" / "intel") if base_dir else DATA_DIR / "intel"
    account_slug = _slugify(account)
    strategy_files = [path for path in _latest_files(business_root / "strategy_outputs", limit=10) if account_slug in path.stem][:5]
    column_asset_files = [path for path in _latest_files(business_root / "columns", limit=20) if account_slug in path.stem][:10]
    sales_files = _latest_files(intel_root / "sales", limit=10)
    feedback_files = _latest_files(intel_root / "feedback", limit=10)

    portfolio_columns: list[dict[str, Any]] = []
    for record in column_records:
        attrs = record.get("attributes") or {}
        column_name = str(attrs.get("column") or record.get("object_id") or "").strip()
        if not column_name:
            continue
        recent_allocs = []
        for allocation in relevant_allocations:
            for item in allocation.get("allocations", []):
                if str(item.get("column") or "").strip() == column_name:
                    recent_allocs.append(
                        {
                            "date": allocation.get("date"),
                            "slot_index": item.get("slot_index"),
                            "role": item.get("role"),
                            "lifecycle_state": item.get("lifecycle_state"),
                            "score": item.get("score"),
                        }
                    )
        column_signals: list[str] = []
        for path in strategy_files + column_asset_files + sales_files + feedback_files:
            text = _read_text(path)
            if column_name and column_name in text:
                column_signals.append(str(path))
        recommendation = "maintain"
        state = str(record.get("state") or "")
        if state == "paused":
            recommendation = "resume_or_retire"
        elif state == "deprecated":
            recommendation = "keep_stopped"
        elif state == "incubating":
            recommendation = "continue_small_experiments"
        elif state == "active_traffic":
            recommendation = "keep_as_traffic_support"
        elif state == "active_revenue":
            recommendation = "keep_as_revenue_column"

        portfolio_columns.append(
            {
                "column": column_name,
                "lifecycle_state": state,
                "role": attrs.get("role"),
                "notes": record.get("notes"),
                "updated_at": record.get("updated_at"),
                "recent_allocations": recent_allocs[:5],
                "signal_matches": column_signals[:8],
                "recommendation": recommendation,
            }
        )

    lifecycle_counts: dict[str, int] = defaultdict(int)
    for item in portfolio_columns:
        lifecycle_counts[str(item.get("lifecycle_state") or "unknown")] += 1

    payload = {
        "date": date,
        "account": account,
        "column_count": len(portfolio_columns),
        "lifecycle_counts": dict(lifecycle_counts),
        "columns": portfolio_columns,
        "allocation_files": [str(path) for path in allocation_files if account in _read_text(path)],
        "strategy_files": [str(path) for path in strategy_files],
        "column_asset_files": [str(path) for path in column_asset_files],
        "sales_files": [str(path) for path in sales_files],
        "feedback_files": [str(path) for path in feedback_files],
        "generated_at": _utc_now_iso(),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 专栏组合经营复盘",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 专栏数: {len(portfolio_columns)}",
        "",
        "## 生命周期统计",
    ]
    for key, value in sorted(lifecycle_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    for item in portfolio_columns:
        lines.extend(
            [
                f"## {item['column']}",
                f"- 生命周期状态: {item['lifecycle_state']}",
                f"- 经营角色: {item['role']}",
                f"- 建议动作: {item['recommendation']}",
                f"- 备注: {item['notes']}",
            ]
        )
        if item["recent_allocations"]:
            lines.append("- 最近分配:")
            for alloc in item["recent_allocations"]:
                lines.append(f"  - {alloc['date']} 槽位{alloc['slot_index']} role={alloc['role']} score={alloc['score']}")
        if item["signal_matches"]:
            lines.append("- 信号来源:")
            for signal in item["signal_matches"][:5]:
                lines.append(f"  - {signal}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    state_path = upsert_state_record(
        object_type="column_allocation",
        object_id=f"portfolio-review__{date}__{_slugify(account)}",
        state="reviewed",
        notes="column portfolio review generated",
        source_path=str(json_path),
        attributes={"date": date, "account": account, "column_count": len(portfolio_columns)},
        base_dir=base_dir,
    )
    return {"json_path": json_path, "md_path": md_path, "state_path": state_path}


def _load_all_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    ledger_root = root / "ledger"
    for object_type in STATE_OBJECT_TYPES:
        for file_path in sorted((ledger_root / object_type).glob("*.json")):
            try:
                record = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            record["record_path"] = str(file_path)
            records.append(record)
    return records


def snapshot_state(*, date: str, base_dir: Path | None, account: str | None = None) -> Path:
    root = ensure_state_directories(base_dir)
    records = _load_all_records(root)

    counts: dict[str, int] = defaultdict(int)
    state_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_object_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        attributes = record.get("attributes") or {}
        if account and isinstance(attributes, dict):
            record_account = str(attributes.get("account") or "").strip()
            if record_account and record_account != account:
                continue
        object_type = str(record.get("object_type", "unknown"))
        state = str(record.get("state", "unknown"))
        counts[object_type] += 1
        state_counts[object_type][state] += 1
        by_object_type[object_type].append(record)

    json_payload = {
        "date": date,
        "account": account,
        "counts": dict(counts),
        "state_counts": {key: dict(value) for key, value in state_counts.items()},
        "records": records,
    }

    snapshot_dir = root / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    json_path = snapshot_dir / f"{date}.json"
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_lines = ["# 状态快照", "", f"- 日期: {date}"]
    if account:
        md_lines.append(f"- 账号: {account}")
    md_lines.append("")

    for object_type in STATE_OBJECT_TYPES:
        md_lines.append(f"## {object_type}")
        md_lines.append(f"- 记录数: {counts.get(object_type, 0)}")
        type_states = state_counts.get(object_type, {})
        if type_states:
            for state_name, count in sorted(type_states.items()):
                md_lines.append(f"- {state_name}: {count}")
        else:
            md_lines.append("- 暂无记录")
        if by_object_type.get(object_type):
            for record in by_object_type[object_type][:3]:
                md_lines.append(
                    f"  - {record.get('object_id')} :: {record.get('state')}"
                )
        md_lines.append("")

    md_path = snapshot_dir / f"{date}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return md_path


def state_history_path(*, object_type: str, object_id: str, base_dir: Path | None) -> Path:
    root = ensure_state_directories(base_dir)
    return _history_file(root, object_type, object_id)
