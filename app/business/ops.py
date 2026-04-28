from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.config import DATA_DIR

BUSINESS_CATEGORIES = (
    "topic_briefs",
    "decisions",
    "playbooks",
    "topic_batches",
    "learning_rules",
    "strategy_outputs",
    "strategy_proposals",
    "columns",
)


def resolve_business_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "business"
    return base_dir / "data" / "business"


def ensure_business_directories(base_dir: Path | None) -> Path:
    root = resolve_business_root(base_dir)
    for category in BUSINESS_CATEGORIES:
        (root / category).mkdir(parents=True, exist_ok=True)
    return root


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "untitled"


def _write_business_record(
    *,
    category: str,
    date: str,
    title: str,
    body_lines: Iterable[str],
    base_dir: Path | None,
    file_stem: str,
) -> Path:
    root = ensure_business_directories(base_dir)
    output_dir = root / category
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date}_{file_stem}.md"

    lines = [f"# {title}", "", f"- 日期: {date}"]
    lines.extend(body_lines)
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def create_topic_brief(
    *,
    date: str,
    account: str,
    title: str,
    audience: str,
    column: str,
    angle: str,
    value: str,
    cta: str,
    source_inputs: list[str] | None,
    why_now: str | None,
    strategy_path: Path | None = None,
    column_asset_path: Path | None = None,
    base_dir: Path | None,
) -> Path:
    body_lines = [
        f"- 账号: {account}",
        f"- 目标读者: {audience}",
        f"- 专栏/栏目: {column}",
        f"- 切入角度: {angle}",
        f"- 价值判断: {value}",
        f"- CTA: {cta}",
    ]
    if why_now:
        body_lines.append(f"- 为什么现在发: {why_now}")
    if strategy_path:
        body_lines.append(f"- 策略输出: {strategy_path}")
    if column_asset_path:
        body_lines.append(f"- 专栏资产: {column_asset_path}")
    if source_inputs:
        body_lines.append("- 参考输入:")
        for item in source_inputs:
            body_lines.append(f"  - {item}")

    body_lines.extend(
        [
            "",
            "## 这篇内容为什么值得写",
            f"- {value}",
            "",
            "## 它给谁看",
            f"- {audience}",
            "",
            "## 它怎么卖专栏",
            f"- {cta}",
        ]
    )

    file_stem = _slugify(title)
    return _write_business_record(
        category="topic_briefs",
        date=date,
        title=f"业务层选题决策：{title}",
        body_lines=body_lines,
        base_dir=base_dir,
        file_stem=file_stem,
    )


def build_strategy_output(
    *,
    date: str,
    account: str,
    stage_goal: str,
    target_column: str,
    strategy_summary: str,
    inputs: list[str] | None,
    adjustments: list[str] | None,
    competitor_insights: list[str] | None,
    proposal_source_path: Path | None = None,
    base_dir: Path | None,
) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    out_dir = root / "strategy_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date}_{_slugify(account)}_strategy"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = {
        "date": date,
        "account": account,
        "stage_goal": stage_goal,
        "target_column": target_column,
        "strategy_summary": strategy_summary,
        "inputs": inputs or [],
        "adjustments": adjustments or [],
        "competitor_insights": competitor_insights or [],
        "proposal_source_path": str(proposal_source_path) if proposal_source_path else None,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 选题策略输出",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 当前阶段目标: {stage_goal}",
        f"- 目标专栏: {target_column}",
        f"- 策略摘要: {strategy_summary}",
    ]
    if proposal_source_path:
        lines.append(f"- 批准来源: {proposal_source_path}")
    lines.extend([
        "",
        "## 输入依据",
    ])
    for item in inputs or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 需要强化/调整"])
    for item in adjustments or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 同类专栏/竞品启发"])
    for item in competitor_insights or ["暂无"]:
        lines.append(f"- {item}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json_path": json_path, "md_path": md_path}


def propose_strategy_change(
    *,
    date: str,
    account: str,
    stage_goal: str,
    target_column: str,
    current_summary: str | None,
    proposed_summary: str,
    reasons: list[str] | None,
    expected_effects: list[str] | None,
    risks: list[str] | None,
    source_signals: list[str] | None,
    base_dir: Path | None,
) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    out_dir = root / "strategy_proposals"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date}_{_slugify(account)}_strategy-proposal"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = {
        "date": date,
        "account": account,
        "stage_goal": stage_goal,
        "target_column": target_column,
        "current_summary": current_summary,
        "proposed_summary": proposed_summary,
        "reasons": reasons or [],
        "expected_effects": expected_effects or [],
        "risks": risks or [],
        "source_signals": source_signals or [],
        "status": "pending_approval",
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 策略变更简报",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 当前阶段目标: {stage_goal}",
        f"- 目标专栏: {target_column}",
        f"- 当前策略摘要: {current_summary or '暂无正式版本'}",
        f"- 建议策略摘要: {proposed_summary}",
        f"- 状态: pending_approval",
        "",
        "## 为什么建议改",
    ]
    for item in reasons or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 预计影响"])
    for item in expected_effects or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 风险与注意点"])
    for item in risks or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 来源信号"])
    for item in source_signals or ["暂无"]:
        lines.append(f"- {item}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json_path": json_path, "md_path": md_path}


def approve_strategy_change(*, proposal_path: Path, base_dir: Path | None) -> dict[str, Path]:
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["status"] = "approved"
    proposal["approved_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    proposal_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

    strategy_paths = build_strategy_output(
        date=str(proposal["date"]),
        account=str(proposal["account"]),
        stage_goal=str(proposal["stage_goal"]),
        target_column=str(proposal["target_column"]),
        strategy_summary=str(proposal["proposed_summary"]),
        inputs=list(proposal.get("source_signals") or []),
        adjustments=list(proposal.get("expected_effects") or []),
        competitor_insights=list(proposal.get("reasons") or []),
        proposal_source_path=proposal_path,
        base_dir=base_dir,
    )
    return {"proposal_path": proposal_path, **strategy_paths}


def _latest_files(directory: Path, limit: int = 3) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def _read_bullets(path: Path, limit: int = 4) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    bullets = [line[2:].strip() for line in lines if line.startswith("- ")]
    return bullets[:limit]


def _latest_strategy_output_summary(root: Path, account: str | None = None) -> str | None:
    files = _latest_files(root / "strategy_outputs", limit=10)
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else None
        except json.JSONDecodeError:
            payload = None
        if payload and (account is None or payload.get("account") == account):
            summary = payload.get("strategy_summary")
            if isinstance(summary, str):
                return summary
    for path in files:
        if account and _slugify(account) not in path.stem:
            continue
        bullets = _read_bullets(path, limit=6)
        for bullet in bullets:
            if bullet.startswith("策略摘要:"):
                return bullet.split(":", 1)[1].strip()
    return None


def auto_propose_strategy_change(
    *,
    date: str,
    account: str,
    stage_goal: str,
    target_column: str,
    base_dir: Path | None,
) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    intel_root = (base_dir / "data" / "intel") if base_dir else DATA_DIR / "intel"

    current_summary = _latest_strategy_output_summary(root, account=account)

    insight_files = _latest_files(intel_root / "insights", limit=2)
    sales_files = _latest_files(intel_root / "sales", limit=2)
    competitor_files = _latest_files(intel_root / "competitors", limit=2)
    column_files = [path for path in _latest_files(root / "columns", limit=10) if _slugify(account) in path.stem][:2]

    source_signals: list[str] = []
    reasons: list[str] = []
    expected_effects: list[str] = []
    risks: list[str] = []

    for path in insight_files + sales_files + competitor_files + column_files:
        source_signals.append(str(path))
        for bullet in _read_bullets(path, limit=3):
            source_signals.append(f"{path.name}: {bullet}")

    if insight_files:
        reasons.append("最近经营复盘已形成新的经营判断，适合转成更明确的选题策略。")
    if sales_files:
        reasons.append("近期专栏/转化信号可用于调整引流题、信任题、转化题的比例。")
        expected_effects.append("提高与专栏转化链路更贴近的题目占比。")
    if competitor_files:
        reasons.append("同类专栏/竞品最近有可迁移的结构启发，应吸收进当前策略。")
        expected_effects.append("让选题更贴近已验证有效的结构和切角。")
    if column_files:
        reasons.append("专栏资产与空缺图显示当前专栏仍有未覆盖缺口，需要纳入新策略。")
        expected_effects.append("优先补齐当前目标专栏的关键空缺。")

    if not reasons:
        reasons.append("检测到需要建立一份正式策略基线，以便后续选题批次有稳定上游输入。")
        expected_effects.append("让后续 topic batch 更稳定地受同一策略约束。")

    proposed_summary = "优先围绕当前目标专栏的空缺，结合近期反馈、转化信号和同类专栏启发，输出更具体、更可转化、避免重复的选题。"
    risks.append("如果近期信号样本过少，策略变更可能过拟合短期数据。")
    risks.append("若专栏空缺判断不准确，可能导致选题偏离真正的转化重点。")

    return propose_strategy_change(
        date=date,
        account=account,
        stage_goal=stage_goal,
        target_column=target_column,
        current_summary=current_summary,
        proposed_summary=proposed_summary,
        reasons=reasons,
        expected_effects=expected_effects,
        risks=risks,
        source_signals=source_signals,
        base_dir=base_dir,
    )


def build_column_asset(
    *,
    date: str,
    account: str,
    column: str,
    goal: str,
    existing_topics: list[str],
    gap_topics: list[str],
    topic_roles: list[str] | None,
    competitor_references: list[str] | None,
    base_dir: Path | None,
) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    out_dir = root / "columns"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date}_{_slugify(account)}_{_slugify(column)}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = {
        "date": date,
        "account": account,
        "column": column,
        "goal": goal,
        "existing_topics": existing_topics,
        "gap_topics": gap_topics,
        "topic_roles": topic_roles or [],
        "competitor_references": competitor_references or [],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 专栏资产与空缺图",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 专栏: {column}",
        f"- 当前目标: {goal}",
        "",
        "## 已有题目",
    ]
    for item in existing_topics or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 当前空缺"])
    for item in gap_topics or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 角色配置"])
    for item in topic_roles or ["暂无"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 同类专栏参考"])
    for item in competitor_references or ["暂无"]:
        lines.append(f"- {item}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json_path": json_path, "md_path": md_path}


def _topic_title_key(title: str) -> str:
    return _slugify(title)


def _topic_usage_dir(root: Path) -> Path:
    path = root / "topic_usage"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _topic_usage_ledger_path(root: Path) -> Path:
    return _topic_usage_dir(root) / "topic_usage_ledger.json"


def _topic_usage_history_path(root: Path, month: str) -> Path:
    return _topic_usage_dir(root) / f"topic_usage_history_{month}.md"


def _load_topic_usage_ledger(root: Path) -> dict[str, object]:
    path = _topic_usage_ledger_path(root)
    if not path.exists():
        return {"entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"entries": []}
    if not isinstance(payload, dict):
        return {"entries": []}
    entries = payload.get("entries")
    if not isinstance(entries, list):
        payload["entries"] = []
    return payload


def _save_topic_usage_ledger(root: Path, payload: dict[str, object]) -> Path:
    path = _topic_usage_ledger_path(root)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _find_topic_in_batch(batch: dict[str, object], topic_number: int) -> dict[str, object]:
    topics = batch.get("topics")
    if not isinstance(topics, list):
        raise ValueError("topic batch has no topics list")
    for item in topics:
        if isinstance(item, dict) and int(item.get("number", 0)) == topic_number:
            return item
    raise ValueError(f"topic #{topic_number} not found in batch")


def is_topic_used(*, title: str, base_dir: Path | None, account: str | None = None) -> bool:
    root = ensure_business_directories(base_dir)
    ledger = _load_topic_usage_ledger(root)
    title_key = _topic_title_key(title)
    for entry in ledger.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("title_key") != title_key:
            continue
        if account and entry.get("account") not in (None, account):
            continue
        if entry.get("status") in {"approved", "used", "published"}:
            return True
    return False


def mark_topic_used(
    *,
    date: str,
    batch_path: Path,
    topic_number: int,
    status: str,
    base_dir: Path | None,
    account: str | None = None,
    notes: str | None = None,
) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    topic = _find_topic_in_batch(batch, topic_number)
    ledger = _load_topic_usage_ledger(root)
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]

    resolved_account = account or str(topic.get("account") or batch.get("account") or "技术小甜甜")
    title = str(topic.get("title") or f"topic-{topic_number}")
    title_key = _topic_title_key(title)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    existing = next(
        (
            entry
            for entry in entries
            if entry.get("title_key") == title_key and entry.get("account") == resolved_account
        ),
        None,
    )
    if existing is None:
        existing = {
            "title_key": title_key,
            "title": title,
            "account": resolved_account,
            "created_at": now,
            "history": [],
        }
        entries.append(existing)

    history = existing.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        existing["history"] = history
    history.append(
        {
            "date": date,
            "status": status,
            "batch_path": str(batch_path),
            "topic_number": topic_number,
            "notes": notes,
            "timestamp": now,
        }
    )

    existing.update(
        {
            "title": title,
            "account": resolved_account,
            "column": topic.get("column"),
            "role": topic.get("role"),
            "priority": topic.get("priority"),
            "status": status,
            "last_batch_path": str(batch_path),
            "last_topic_number": topic_number,
            "updated_at": now,
            "notes": notes,
        }
    )

    ledger["updated_at"] = now
    ledger["entries"] = entries
    ledger_path = _save_topic_usage_ledger(root, ledger)

    month = date[:7]
    history_path = _topic_usage_history_path(root, month)
    history_lines = history_path.read_text(encoding="utf-8").splitlines() if history_path.exists() else ["# 选题使用历史", ""]
    history_lines.extend(
        [
            f"## {date}",
            f"- 标题: {title}",
            f"- 账号: {resolved_account}",
            f"- 状态: {status}",
            f"- 批次文件: {batch_path}",
            f"- 题号: {topic_number}",
            f"- 备注: {notes or '无'}",
            "",
        ]
    )
    history_path.write_text("\n".join(history_lines), encoding="utf-8")

    return {"ledger_path": ledger_path, "history_path": history_path}


def topic_usage_report(*, date: str, base_dir: Path | None, account: str | None = None) -> Path:
    root = ensure_business_directories(base_dir)
    report_dir = root / "playbooks"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{date}-topic-usage-report.md"
    ledger = _load_topic_usage_ledger(root)
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]
    if account:
        entries = [entry for entry in entries if entry.get("account") == account]

    status_counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        status_counts[str(entry.get("status", "unknown"))] += 1

    lines = ["# 选题使用报告", "", f"- 日期: {date}"]
    if account:
        lines.append(f"- 账号: {account}")
    lines.append(f"- 已记录选题数: {len(entries)}")
    lines.append("")
    lines.append("## 状态统计")
    if status_counts:
        for status_name, count in sorted(status_counts.items()):
            lines.append(f"- {status_name}: {count}")
    else:
        lines.append("- 暂无记录")
    lines.append("")
    lines.append("## 最近选题")
    if not entries:
        lines.append("- 暂无记录")
    else:
        recent = sorted(entries, key=lambda item: str(item.get("updated_at", "")), reverse=True)
        for entry in recent[:10]:
            lines.append(
                f"- {entry.get('title')} :: {entry.get('status')} :: {entry.get('account')}"
            )
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def validate_topic_batch_payload(batch: dict[str, object]) -> dict[str, object]:
    required_top_level = ["account", "generated_at", "batch_strategy", "writing_order", "topics"]
    missing = [key for key in required_top_level if key not in batch]
    if missing:
        raise ValueError(f"topic batch missing required fields: {', '.join(missing)}")

    topics = batch.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("topic batch must contain a non-empty topics list")
    if len(topics) != 8:
        raise ValueError("topic batch must contain exactly 8 topics")

    required_topic_fields = [
        "number",
        "title",
        "audience",
        "account",
        "column",
        "reason",
        "expected_value",
        "why_now",
        "cta",
        "role",
        "risk",
        "priority",
    ]
    for index, topic in enumerate(topics, start=1):
        if not isinstance(topic, dict):
            raise ValueError(f"topic #{index} must be an object")
        missing_topic_fields = [field for field in required_topic_fields if field not in topic]
        if missing_topic_fields:
            raise ValueError(
                f"topic #{index} missing required fields: {', '.join(missing_topic_fields)}"
            )

    return batch


def _topic_batch_stem(date: str, generated_at: str | None = None) -> str:
    if generated_at:
        compact = re.sub(r"[^0-9]", "", generated_at)
        if len(compact) >= 14:
            return f"topic-batch_{compact[:14]}"
    return f"topic-batch_{date.replace('-', '')}_090000"


def write_topic_batch_files(*, batch: dict[str, object], date: str, base_dir: Path | None) -> dict[str, Path]:
    validated = validate_topic_batch_payload(batch)
    root = ensure_business_directories(base_dir)
    output_dir = root / "topic_batches"
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = _topic_batch_stem(date, str(validated.get("generated_at") or ""))
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"

    json_path.write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_batch(md_path, validated, "选题批次")
    return {"json_path": json_path, "md_path": md_path}


def summarize_business_inputs(root: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for category in BUSINESS_CATEGORIES:
        category_dir = root / category
        if not category_dir.exists():
            continue
        for file_path in sorted(category_dir.glob("*.md")):
            grouped[category].append(file_path)
    return grouped


def _append_category_section(lines: list[str], title: str, files: list[Path], root: Path) -> None:
    lines.append(f"## {title}")
    if not files:
        lines.append("- 暂无记录")
        lines.append("")
        return

    lines.append(f"- 记录数: {len(files)}")
    for file_path in files:
        lines.append(f"- {file_path.relative_to(root)}")
        try:
            content = file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        title_line = next((line[2:].strip() for line in content if line.startswith("# ")), None)
        if title_line:
            lines.append(f"  - 标题: {title_line}")

        bullets = [line[2:].strip() for line in content if line.startswith("- ")]
        for bullet in bullets[:3]:
            lines.append(f"  - {bullet}")
    lines.append("")


def review_business(*, date: str, base_dir: Path | None, account: str | None = None) -> Path:
    root = ensure_business_directories(base_dir)
    output_dir = root / "playbooks"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date}-business-review.md"

    grouped = summarize_business_inputs(root)
    lines = ["# 业务层复盘", "", f"- 日期: {date}"]
    if account:
        lines.append(f"- 账号: {account}")
    lines.append("")

    _append_category_section(lines, "选题决策", grouped.get("topic_briefs", []), root)
    _append_category_section(lines, "经营决策", grouped.get("decisions", []), root)

    lines.append("## 业务层结论")
    lines.append("- 哪些题更适合新号技术小甜甜")
    lines.append("- 哪些题更适合旧号踏雪无痕老爷子")
    lines.append("- 哪些题应当优先导向专栏转化")
    lines.append("")

    lines.append("## 下一步动作")
    lines.append("- 把高价值题拆成可执行发布任务")
    lines.append("- 让选题直接带着目标读者、账号和专栏归属")
    lines.append("- 继续把低效题从内容池中剔除")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _normalize_feedback_rules(feedback: str) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    normalized = feedback.replace("\n", " ")

    if "少来" in normalized and ("概念题" in normalized or "纯概念题" in normalized):
        rules.append(
            {
                "rule_type": "downweight",
                "pattern": "纯概念题",
                "reason": "用户明确要求减少纯概念题",
            }
        )
    if ("多来一点" in normalized or "提高" in normalized) and ("专栏点击" in normalized or "转化" in normalized):
        rules.append(
            {
                "rule_type": "upweight",
                "pattern": "高转化题",
                "reason": "用户希望提高专栏点击或转化相关题材占比",
            }
        )
    if "实操" in normalized or "避坑" in normalized:
        rules.append(
            {
                "rule_type": "upweight",
                "pattern": "实操避坑题",
                "reason": "用户偏好更具体、更可执行的实操题",
            }
        )
    if "新号" in normalized:
        rules.append(
            {
                "rule_type": "prefer_account",
                "pattern": "技术小甜甜",
                "reason": "用户反馈涉及新号优先承接相关题材",
            }
        )
    return rules


def _extract_topic_actions(batch: dict[str, object], feedback: str) -> list[dict[str, object]]:
    topics = batch.get("topics", [])
    if not isinstance(topics, list):
        return []

    actions: list[dict[str, object]] = []
    for match in re.finditer(r"第\s*(\d+)\s*个([^。！？\n]*)", feedback):
        topic_number = int(match.group(1))
        fragment = match.group(0).strip()
        topic = next(
            (
                item
                for item in topics
                if isinstance(item, dict) and int(item.get("number", 0)) == topic_number
            ),
            None,
        )
        if topic is None:
            continue

        action = "revise"
        if any(token in fragment for token in ("不要", "删", "删除", "去掉")):
            action = "delete"
        elif "保留" in fragment and "改" not in fragment:
            action = "keep"
        elif "升" in fragment or "提前" in fragment or "优先" in fragment:
            action = "promote"
        elif "降" in fragment or "延后" in fragment:
            action = "demote"

        actions.append(
            {
                "topic_number": topic_number,
                "title": topic.get("title"),
                "action": action,
                "user_feedback": fragment,
                "system_interpretation": _interpret_topic_action(fragment, action),
            }
        )
    return actions


def _interpret_topic_action(fragment: str, action: str) -> str:
    if action == "delete":
        return "从当前批次移除该选题，并把对应题型视为降权候选。"
    if action == "promote":
        return "保留该选题，并提高在当前批次中的执行优先级。"
    if action == "demote":
        return "保留该选题，但降低优先级或延后到后续批次。"
    if action == "keep":
        return "保持该选题方向不变。"
    if "实操" in fragment or "避坑" in fragment:
        return "保留主题，但改写为更偏实操避坑的切角。"
    return "保留主题，并根据反馈调整标题或切角。"


def _usage_status_from_action(action: str) -> str:
    if action == "delete":
        return "rejected"
    return "approved"


def _feedback_indicates_batch_approval(feedback: str) -> bool:
    normalized = feedback.replace("\n", " ")
    positive_markers = ("这一批可以", "这批可以", "都可以", "通过", "没问题", "照这个来", "可以直接用")
    negative_markers = ("不要", "删除", "去掉", "太泛", "不行", "不通过")
    return any(token in normalized for token in positive_markers) and not any(
        token in normalized for token in negative_markers
    )


def _sync_topic_actions_to_usage(
    *,
    date: str,
    batch_path: Path,
    batch: dict[str, object],
    topic_actions: list[dict[str, object]],
    feedback: str,
    base_dir: Path | None,
    account: str | None,
) -> list[dict[str, object]]:
    synced: list[dict[str, object]] = []
    handled_numbers = {int(item["topic_number"]) for item in topic_actions}

    for item in topic_actions:
        status = _usage_status_from_action(str(item["action"]))
        notes = f"来自用户反馈自动同步: {item['user_feedback']}"
        mark_topic_used(
            date=date,
            batch_path=batch_path,
            topic_number=int(item["topic_number"]),
            status=status,
            account=account,
            notes=notes,
            base_dir=base_dir,
        )
        synced.append(
            {
                "topic_number": int(item["topic_number"]),
                "title": item.get("title"),
                "status": status,
                "reason": notes,
            }
        )

    if _feedback_indicates_batch_approval(feedback):
        topics = batch.get("topics", []) if isinstance(batch.get("topics"), list) else []
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            topic_number = int(topic.get("number", 0))
            if topic_number in handled_numbers:
                continue
            notes = "来自用户反馈自动同步: 整批通过/可用"
            mark_topic_used(
                date=date,
                batch_path=batch_path,
                topic_number=topic_number,
                status="approved",
                account=account,
                notes=notes,
                base_dir=base_dir,
            )
            synced.append(
                {
                    "topic_number": topic_number,
                    "title": topic.get("title"),
                    "status": "approved",
                    "reason": notes,
                }
            )

    return synced


def _apply_topic_actions(batch: dict[str, object], actions: list[dict[str, object]]) -> dict[str, object]:
    revised = json.loads(json.dumps(batch, ensure_ascii=False))
    topics = revised.get("topics", [])
    if not isinstance(topics, list):
        revised["topics"] = []
        return revised

    action_map = {int(item["topic_number"]): item for item in actions}
    kept_topics: list[dict[str, object]] = []
    for item in topics:
        if not isinstance(item, dict):
            continue
        number = int(item.get("number", 0))
        action = action_map.get(number)
        if action is None:
            kept_topics.append(item)
            continue
        if action["action"] == "delete":
            continue
        if action["action"] == "promote":
            item["priority"] = "主推"
        if action["action"] == "demote":
            item["priority"] = "备用"
        if action["action"] == "revise":
            item["revision_note"] = str(action["system_interpretation"])
        kept_topics.append(item)

    for index, item in enumerate(kept_topics, start=1):
        item["number"] = index
    revised["topics"] = kept_topics
    revised["revision_summary"] = [item["system_interpretation"] for item in actions]
    return revised


def _write_markdown_batch(path: Path, batch: dict[str, object], heading: str) -> None:
    topics = batch.get("topics", []) if isinstance(batch.get("topics"), list) else []
    lines = [f"# {heading}", ""]
    if batch.get("account"):
        lines.append(f"- 账号: {batch['account']}")
    if batch.get("generated_at"):
        lines.append(f"- 生成时间: {batch['generated_at']}")
    if batch.get("batch_strategy"):
        lines.append(f"- 批次策略: {batch['batch_strategy']}")
    lines.append(f"- 选题数: {len(topics)}")
    lines.append("")

    writing_order = batch.get("writing_order")
    if isinstance(writing_order, list) and writing_order:
        lines.append("## 建议写作顺序")
        for item in writing_order:
            lines.append(f"- {item}")
        lines.append("")

    changes = batch.get("changes_from_previous")
    if isinstance(changes, list) and changes:
        lines.append("## 相比上一批的变化")
        for item in changes:
            lines.append(f"- {item}")
        lines.append("")

    for item in topics:
        if not isinstance(item, dict):
            continue
        lines.append(f"## {item.get('number', '?')}. {item.get('title', '未命名选题')}")
        lines.append(f"- 优先级: {item.get('priority', '未设置')}")
        if item.get("audience"):
            lines.append(f"- 目标读者: {item['audience']}")
        if item.get("account"):
            lines.append(f"- 账号: {item['account']}")
        if item.get("column"):
            lines.append(f"- 专栏/系列: {item['column']}")
        if item.get("reason"):
            lines.append(f"- 选择理由: {item['reason']}")
        if item.get("expected_value"):
            lines.append(f"- 预期价值: {item['expected_value']}")
        if item.get("why_now"):
            lines.append(f"- 为什么现在写: {item['why_now']}")
        if item.get("cta"):
            lines.append(f"- CTA: {item['cta']}")
        if item.get("role"):
            lines.append(f"- 题型角色: {item['role']}")
        if item.get("risk"):
            lines.append(f"- 风险/不确定点: {item['risk']}")
        if item.get("revision_note"):
            lines.append(f"- 修订说明: {item['revision_note']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def process_topic_batch_feedback(
    *,
    date: str,
    batch_path: Path,
    feedback: str,
    base_dir: Path | None,
    account: str | None = None,
) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    feedback_root = (base_dir / "data" / "intel") if base_dir else DATA_DIR / "intel"
    (feedback_root / "feedback").mkdir(parents=True, exist_ok=True)
    batch_dir = root / "topic_batches"
    learning_dir = root / "learning_rules"
    batch_dir.mkdir(parents=True, exist_ok=True)
    learning_dir.mkdir(parents=True, exist_ok=True)

    raw_batch = json.loads(batch_path.read_text(encoding="utf-8"))
    inferred_account = account or str(raw_batch.get("account") or "技术小甜甜")
    timestamp = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d") + "_090000"

    topic_actions = _extract_topic_actions(raw_batch, feedback)
    normalized_rules = _normalize_feedback_rules(feedback)
    synced_usage = _sync_topic_actions_to_usage(
        date=date,
        batch_path=batch_path,
        batch=raw_batch,
        topic_actions=topic_actions,
        feedback=feedback,
        account=account,
        base_dir=base_dir,
    )
    revised_batch = _apply_topic_actions(raw_batch, topic_actions)
    revised_batch["account"] = inferred_account
    revised_batch["feedback"] = feedback
    revised_batch["learned_rules"] = normalized_rules
    revised_batch["usage_sync"] = synced_usage

    feedback_json_path = feedback_root / "feedback" / f"topic-batch-feedback_{timestamp}.json"
    feedback_md_path = feedback_root / "feedback" / f"topic-batch-feedback_{timestamp}.md"
    revised_json_path = batch_dir / f"topic-batch_{timestamp}.revised.json"
    revised_md_path = batch_dir / f"topic-batch_{timestamp}.revised.md"
    rules_json_path = learning_dir / "topic_learning_rules.json"
    history_md_path = learning_dir / f"topic_learning_history_{date[:7]}.md"

    feedback_payload = {
        "date": date,
        "account": inferred_account,
        "batch_path": str(batch_path),
        "user_feedback": feedback,
        "topic_actions": topic_actions,
        "normalized_rules": normalized_rules,
        "usage_sync": synced_usage,
    }
    feedback_json_path.write_text(json.dumps(feedback_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    feedback_lines = [
        "# 选题批次反馈记录",
        "",
        f"- 日期: {date}",
        f"- 账号: {inferred_account}",
        f"- 批次文件: {batch_path}",
        f"- 用户原话: {feedback}",
        "",
        "## 题目级反馈",
    ]
    if not topic_actions:
        feedback_lines.append("- 无明确题号反馈，已仅提炼通用规则")
    else:
        for item in topic_actions:
            feedback_lines.append(
                f"- 第{item['topic_number']}个《{item['title']}》: {item['action']} / {item['system_interpretation']}"
            )
    feedback_lines.extend(["", "## 规则级反馈"])
    if not normalized_rules:
        feedback_lines.append("- 暂无新增长期规则")
    else:
        for rule in normalized_rules:
            feedback_lines.append(f"- {rule['rule_type']} {rule['pattern']}: {rule['reason']}")
    feedback_lines.extend(["", "## 使用状态自动同步"])
    if not synced_usage:
        feedback_lines.append("- 本轮未触发 topic usage 自动状态变化")
    else:
        for item in synced_usage:
            feedback_lines.append(
                f"- 第{item['topic_number']}个《{item['title']}》 -> {item['status']} ({item['reason']})"
            )
    feedback_lines.append("")
    feedback_md_path.write_text("\n".join(feedback_lines), encoding="utf-8")

    revised_json_path.write_text(json.dumps(revised_batch, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_batch(revised_md_path, revised_batch, "修订后选题批次")

    rules_payload = {"updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z", "rules": normalized_rules}
    rules_json_path.write_text(json.dumps(rules_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    history_lines = []
    if history_md_path.exists():
        history_lines = history_md_path.read_text(encoding="utf-8").splitlines()
    if not history_lines:
        history_lines = ["# 选题学习历史", ""]
    history_lines.extend(
        [
            f"## {date}",
            f"- 用户反馈: {feedback}",
            f"- 影响题目数: {len(topic_actions)}",
            f"- 新规则数: {len(normalized_rules)}",
            "",
        ]
    )
    history_md_path.write_text("\n".join(history_lines), encoding="utf-8")

    return {
        "feedback_json_path": feedback_json_path,
        "feedback_md_path": feedback_md_path,
        "revised_json_path": revised_json_path,
        "revised_md_path": revised_md_path,
        "rules_json_path": rules_json_path,
        "history_md_path": history_md_path,
    }
