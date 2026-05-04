from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

from app.config import DATA_DIR
from app.state import get_column_lifecycle

BUSINESS_CATEGORIES = (
    "topic_briefs",
    "decisions",
    "playbooks",
    "topic_batches",
    "learning_rules",
    "strategy_outputs",
    "strategy_proposals",
    "columns",
    "topic_libraries",
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


def _infer_column_goal_and_gaps(column: str, description: str, existing_topics: list[str]) -> tuple[str, list[str], list[str]]:
    text = f"{column} {description}".lower()
    if "dify" in text:
        return (
            "先把 Dify 主线拆成稳定的结构化篇目，再按使用情况补深度和案例。",
            [
                "基础认知/入口价值篇是否完整",
                "知识库问答结构是否形成系列",
                "工作流自动化是否形成从入门到上线的递进结构",
                "Agent / 多轮状态 / 评审审批等高阶能力是否各自成系列",
            ],
            ["信任题", "引流题", "转化题"],
        )
    if "企业级ai" in text or "模型部署" in text or "应用系统" in text:
        return (
            "形成企业AI落地从部署、架构、流程、评估到上线的完整篇目基线。",
            [
                "部署选型是否覆盖云/本地/内网三类路径",
                "PoC 到生产的工程化链路是否完整",
                "权限、评估、回写、监控是否形成专题",
                "不同业务场景的落地案例是否足够",
            ],
            ["信任题", "转化题"],
        )
    if "python" in text:
        return (
            "把 Python 专栏先做成适合职场实战的基础题库，再补专题深挖。",
            [
                "环境/路径/编码这类高频踩坑是否系统覆盖",
                "自动化、文本处理、脚本工程化是否形成递进结构",
                "从会写脚本到可维护小工具的桥接题是否充足",
            ],
            ["引流题", "信任题"],
        )
    if "技术前沿每日速读" in text:
        return (
            "作为引流专栏，先建立稳定热点结构，再承接到深度专栏。",
            [
                "热点解读模板是否固定",
                "从热点到实战的导流桥接是否成体系",
                "周度/日度速读栏目结构是否稳定",
            ],
            ["引流题"],
        )
    return (
        "先建立该专栏的结构化基线题库，再根据使用反馈补空缺。",
        [
            "当前专栏已有题目是否能归纳出稳定结构",
            "哪些知识点/案例点还没有系统覆盖",
            "是否缺少从引流到转化的桥接题",
        ],
        ["引流题", "信任题", "转化题"],
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


def _should_generate_library_for_column(*, account: str, column: str, base_dir: Path | None) -> tuple[bool, str]:
    lifecycle = get_column_lifecycle(account=account, column=column, base_dir=base_dir)
    if not lifecycle:
        return True, "no lifecycle record -> generate by default"
    state = str(lifecycle.get("state") or "").strip()
    if state == "deprecated":
        return False, "lifecycle=deprecated -> treated as stopped/停刊"
    return True, f"lifecycle={state or 'unknown'} -> generate by default"


def build_baseline_column_assets_from_full_capture(*, date: str, account: str, capture_path: Path, base_dir: Path | None) -> dict[str, object]:
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    columns = payload.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("full capture has no columns to build baseline assets from")

    created: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for column_item in columns:
        if not isinstance(column_item, dict):
            continue
        column = str(column_item.get("title") or "").strip()
        if not column:
            continue
        should_generate, reason = _should_generate_library_for_column(account=account, column=column, base_dir=base_dir)
        if not should_generate:
            skipped.append({"column": column, "reason": reason})
            continue
        description = str(column_item.get("description") or "").strip()
        articles = [item for item in (column_item.get("articles") or []) if isinstance(item, dict)]
        existing_topics = [str(item.get("title") or "").strip() for item in articles if str(item.get("title") or "").strip()][:20]
        goal, gap_topics, topic_roles = _infer_column_goal_and_gaps(column, description, existing_topics)
        competitor_references = [
            f"历史文章数: {len(articles)}",
            f"专栏描述摘要: {description[:120] if description else '暂无'}",
        ]
        result = build_column_asset(
            date=date,
            account=account,
            column=column,
            goal=goal,
            existing_topics=existing_topics,
            gap_topics=gap_topics,
            topic_roles=topic_roles,
            competitor_references=competitor_references,
            base_dir=base_dir,
        )
        created.append({"column": column, "json_path": str(result["json_path"]), "md_path": str(result["md_path"])})

    if not created:
        raise ValueError("no valid columns were found in full capture")
    return {
        "capture_path": str(capture_path),
        "created_count": len(created),
        "assets": created,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


def _existing_topic_text(existing_topics: list[str]) -> str:
    return "\n".join(existing_topics).lower()


def _module_status(*, existing_topics: list[str], keywords: list[str]) -> str:
    if not existing_topics:
        return "missing"
    text = _existing_topic_text(existing_topics)
    hits = sum(1 for keyword in keywords if keyword and keyword.lower() in text)
    if hits >= max(1, len(keywords) // 2):
        return "covered"
    if hits > 0:
        return "partial"
    return "missing"


def _library_blueprint(column: str, description: str) -> list[dict[str, object]]:
    text = f"{column} {description}".lower()
    if "dify" in text:
        return [
            {
                "module": "dify-foundation",
                "name": "Dify 基础认知与入口价值",
                "goal": "先把新手认知、能力边界、适用场景讲清楚。",
                "role": "信任题",
                "keywords": ["入口", "新手", "价值", "边界"],
                "candidate_titles": [
                    "[Dify实战] 为什么很多团队不是不会做 AI，而是没有先搭好可复用的 Dify 入口层？",
                    "[Dify实战] 刚开始做 Dify，先补哪 3 个基础认知，后面才不会一直返工？",
                ],
            },
            {
                "module": "dify-knowledge-rag",
                "name": "知识库 / RAG 问答主线",
                "goal": "把知识库清洗、召回、评估、回写变成连续系列。",
                "role": "信任题",
                "keywords": ["知识库", "rag", "召回", "问答", "摘要"],
                "candidate_titles": [
                    "[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？",
                    "[Dify实战] 做 Dify 知识库时，先补清洗、召回还是评估？很多人顺序都错了",
                ],
            },
            {
                "module": "dify-workflow-automation",
                "name": "工作流自动化主线",
                "goal": "覆盖从节点设计、异常排查到上线闭环。",
                "role": "引流题",
                "keywords": ["工作流", "自动化", "节点", "发布自动化", "纪要"],
                "candidate_titles": [
                    "[Dify实战] 工作流自动化真正难的不是连节点，而是上线后怎么稳定跑下去？",
                    "[Dify实战] 做 Dify 工作流时，为什么越到后面越容易被“人审节点”卡死？",
                ],
            },
            {
                "module": "dify-agent-advanced",
                "name": "Agent / 多轮状态 / 审批闭环高阶主线",
                "goal": "把多轮状态、Agent 取舍、评审审批等高阶专题各自成系列。",
                "role": "转化题",
                "keywords": ["agent", "多轮", "状态", "审批", "评审"],
                "candidate_titles": [
                    "[Dify实战] 多轮状态不是功能点，而是系统设计题：该怎么拆才不会越做越乱？",
                    "[Dify实战] Agent 真正适合接哪类任务？别再把所有问题都往智能体上堆了",
                ],
            },
        ]
    if "企业级ai" in text or "模型部署" in text or "应用系统" in text:
        return [
            {
                "module": "enterprise-deployment",
                "name": "部署选型与基础设施",
                "goal": "形成云/本地/内网环境的部署选型基线。",
                "role": "信任题",
                "keywords": ["部署", "内网", "基础设施", "ollama", "云模型"],
                "candidate_titles": [
                    "[企业AI落地] 如果团队准备正式落地，第一步该先定部署方式还是先定业务场景？",
                    "[企业AI落地] 企业内网做 AI，为什么最先卡住的通常不是模型，而是基础设施边界？",
                ],
            },
            {
                "module": "enterprise-engineering",
                "name": "PoC 到生产的工程化链路",
                "goal": "把评估、权限、监控、回写补成完整篇目。",
                "role": "转化题",
                "keywords": ["poc", "生产", "工程化", "监控", "权限", "评估"],
                "candidate_titles": [
                    "[企业AI落地] PoC 能跑不等于能交付：真正决定项目成败的是哪几段工程链路？",
                    "[企业AI落地] 做企业 AI 应用时，权限、评估、监控、回写到底该先补哪一个？",
                ],
            },
            {
                "module": "enterprise-scenarios",
                "name": "业务场景落地案例",
                "goal": "沉淀可复用的业务案例和行业模板。",
                "role": "转化题",
                "keywords": ["案例", "场景", "应用系统", "知识库", "助手"],
                "candidate_titles": [
                    "[企业AI落地] 业务场景很多，为什么真正值得先做的往往只有两三类？",
                    "[企业AI落地] 从企业助手到知识库系统，怎样判断哪个业务场景最适合先上线？",
                ],
            },
        ]
    if "技术前沿每日速读" in text:
        return [
            {
                "module": "trend-fast-read-template",
                "name": "热点速读模板",
                "goal": "把热点解读做成稳定栏目模板。",
                "role": "引流题",
                "keywords": ["热点", "速读", "变化", "趋势"],
                "candidate_titles": [
                    "[AI] 这周最值得继续追的 3 个 AI / Dify 热点，到底哪一个最可能先落地？",
                    "[AI] 每天都在出新热点，为什么真正值得跟的通常只有少数几条？",
                ],
            },
            {
                "module": "trend-to-depth-bridge",
                "name": "从热点到深度专栏的导流桥接",
                "goal": "让速读位稳定承接到 Dify/企业AI 深度专栏。",
                "role": "引流题",
                "keywords": ["导流", "桥接", "落地", "流程闭环", "企业助手"],
                "candidate_titles": [
                    "[AI] 大家都在聊工作流自动化，真正值得普通团队先学的到底是哪一步？",
                    "[AI] 热点看得很多，为什么一到真正要落地时，还是会回到流程闭环这件事？",
                ],
            },
        ]
    if "python" in text:
        return [
            {
                "module": "python-foundation-pitfalls",
                "name": "环境 / 路径 / 编码高频避坑",
                "goal": "先把新手最容易踩的环境类问题系统覆盖。",
                "role": "引流题",
                "keywords": ["venv", "路径", "编码", "解释器"],
                "candidate_titles": [
                    "[Python实战] 环境问题总是反复踩？其实最该先建立的是哪套排查顺序？",
                    "[Python实战] 路径、编码、解释器老出问题时，怎样把脚本环境一次性理顺？",
                ],
            },
            {
                "module": "python-automation-engineering",
                "name": "自动化脚本到可维护工具",
                "goal": "把脚本工程化、复用化、可维护性补成主线。",
                "role": "信任题",
                "keywords": ["自动化", "脚本", "可维护", "工具"],
                "candidate_titles": [
                    "[Python实战] 一个脚本什么时候该升级成工具？很多人其实判断得太晚了",
                    "[Python实战] 自动化脚本总是越写越散，怎样把它整理成可维护的小系统？",
                ],
            },
        ]
    return [
        {
            "module": "generic-baseline",
            "name": "专栏基线结构",
            "goal": "先形成一个可持续消费的结构化题库。",
            "role": "信任题",
            "keywords": [column],
            "candidate_titles": [
                f"[{column}] 以当前历史内容为基线，这个专栏下一步最该先补哪一类结构题？",
                f"[{column}] 如果要把专栏做成体系，现在哪些篇目应该先进入基线题库？",
            ],
        }
    ]


def build_baseline_topic_library(*, date: str, account: str, column: str, description: str, existing_topics: list[str], base_dir: Path | None) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    out_dir = root / "topic_libraries"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date}_{_slugify(account)}_{_slugify(column)}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    modules = []
    for module in _library_blueprint(column, description):
        status = _module_status(existing_topics=existing_topics, keywords=list(module.get("keywords") or []))
        candidates = []
        for idx, title in enumerate(list(module.get("candidate_titles") or []), start=1):
            candidate_id = f"{_slugify(account)}::{_slugify(column)}::{_slugify(str(module.get('module') or 'module'))}::{idx:02d}"
            candidates.append({
                "candidate_id": candidate_id,
                "title": title,
                "status": "unused",
                "source": "baseline_library",
                "role": module.get("role") or "信任题",
                "module": module.get("module"),
            })
        modules.append(
            {
                "module": module.get("module"),
                "name": module.get("name"),
                "goal": module.get("goal"),
                "role": module.get("role"),
                "status": status,
                "keywords": list(module.get("keywords") or []),
                "candidate_topics": candidates,
            }
        )
    modules = _merge_existing_candidate_state(root=root, account=account, column=column, modules=modules)

    payload = {
        "date": date,
        "account": account,
        "column": column,
        "description": description,
        "existing_topics": existing_topics,
        "modules": modules,
        "library_strategy": "先消耗结构化基线题库，再在空缺上补结构或挖深度。",
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 专栏基线题库",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 专栏: {column}",
        f"- 策略: {payload['library_strategy']}",
        "",
        "## 已有历史题目（截取）",
    ]
    for topic in existing_topics[:12] or ["暂无"]:
        lines.append(f"- {topic}")
    for module in modules:
        lines.extend([
            "",
            f"## {module['name']}",
            f"- 状态: {module['status']}",
            f"- 目标: {module['goal']}",
            f"- 角色: {module['role']}",
            f"- 关键词: {', '.join(module['keywords']) if module['keywords'] else '暂无'}",
            "- 基线候选题:",
        ])
        for candidate in module["candidate_topics"]:
            lines.append(f"  - {candidate['title']} ({candidate['status']})")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json_path": json_path, "md_path": md_path}


def build_baseline_topic_libraries_from_full_capture(*, date: str, account: str, capture_path: Path, base_dir: Path | None) -> dict[str, object]:
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    columns = payload.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("full capture has no columns to build baseline topic libraries from")

    created: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for column_item in columns:
        if not isinstance(column_item, dict):
            continue
        column = str(column_item.get("title") or "").strip()
        if not column:
            continue
        should_generate, reason = _should_generate_library_for_column(account=account, column=column, base_dir=base_dir)
        if not should_generate:
            skipped.append({"column": column, "reason": reason})
            continue
        description = str(column_item.get("description") or "").strip()
        articles = [item for item in (column_item.get("articles") or []) if isinstance(item, dict)]
        existing_topics = [str(item.get("title") or "").strip() for item in articles if str(item.get("title") or "").strip()]
        result = build_baseline_topic_library(
            date=date,
            account=account,
            column=column,
            description=description,
            existing_topics=existing_topics,
            base_dir=base_dir,
        )
        created.append({"column": column, "json_path": str(result["json_path"]), "md_path": str(result["md_path"])})

    if not created:
        raise ValueError("no valid columns were found in full capture")
    return {
        "capture_path": str(capture_path),
        "created_count": len(created),
        "libraries": created,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


def _topic_library_dir(root: Path) -> Path:
    path = root / "topic_libraries"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _topic_library_paths(root: Path, account: str, column: str) -> list[Path]:
    pattern = f"*_{_slugify(account)}_{_slugify(column)}.json"
    return sorted(_topic_library_dir(root).glob(pattern), reverse=True)



def _load_latest_topic_library_payload(*, root: Path, account: str, column: str) -> dict[str, object] | None:
    for path in _topic_library_paths(root, account, column):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None



def _merge_existing_candidate_state(*, root: Path, account: str, column: str, modules: list[dict[str, object]]) -> list[dict[str, object]]:
    previous = _load_latest_topic_library_payload(root=root, account=account, column=column)
    if not previous:
        return modules

    by_candidate_id: dict[str, dict[str, object]] = {}
    by_title_key: dict[str, dict[str, object]] = {}
    for module in previous.get("modules") or []:
        if not isinstance(module, dict):
            continue
        for candidate in module.get("candidate_topics") or []:
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(candidate.get("candidate_id") or "").strip()
            title_key = _topic_title_key(str(candidate.get("title") or ""))
            if candidate_id:
                by_candidate_id[candidate_id] = candidate
            if title_key:
                by_title_key[title_key] = candidate

    for module in modules:
        if not isinstance(module, dict):
            continue
        for candidate in module.get("candidate_topics") or []:
            if not isinstance(candidate, dict):
                continue
            previous_candidate = None
            candidate_id = str(candidate.get("candidate_id") or "").strip()
            if candidate_id:
                previous_candidate = by_candidate_id.get(candidate_id)
            if previous_candidate is None:
                title_key = _topic_title_key(str(candidate.get("title") or ""))
                previous_candidate = by_title_key.get(title_key)
            if previous_candidate is None:
                continue
            if previous_candidate.get("status"):
                candidate["status"] = previous_candidate.get("status")
            if "notes" in previous_candidate:
                candidate["notes"] = previous_candidate.get("notes")
    return modules



def _sync_topic_library_markdown(payload: dict[str, object], md_path: Path) -> None:
    lines = [
        "# 专栏基线题库",
        "",
        f"- 日期: {payload.get('date')}",
        f"- 账号: {payload.get('account')}",
        f"- 专栏: {payload.get('column')}",
        f"- 策略: {payload.get('library_strategy')}",
        "",
        "## 已有历史题目（截取）",
    ]
    for topic in list(payload.get("existing_topics") or [])[:12] or ["暂无"]:
        lines.append(f"- {topic}")
    for module in payload.get("modules") or []:
        if not isinstance(module, dict):
            continue
        lines.extend([
            "",
            f"## {module.get('name')}",
            f"- 状态: {module.get('status')}",
            f"- 目标: {module.get('goal')}",
            f"- 角色: {module.get('role')}",
            f"- 关键词: {', '.join(module.get('keywords') or []) if module.get('keywords') else '暂无'}",
            "- 基线候选题:",
        ])
        for candidate in module.get("candidate_topics") or []:
            if not isinstance(candidate, dict):
                continue
            lines.append(f"  - {candidate.get('title')} ({candidate.get('status')})")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def update_topic_library_candidate_status(*, base_dir: Path | None, account: str, column: str | None, title: str, status: str, notes: str | None = None, candidate_id: str | None = None) -> dict[str, str] | None:
    if base_dir is None or not column:
        return None
    root = ensure_business_directories(base_dir)
    json_paths = _topic_library_paths(root, account, column)
    if not json_paths:
        return None
    title_key = _topic_title_key(title)
    for json_path in json_paths:
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        changed = False
        for module in payload.get("modules") or []:
            if not isinstance(module, dict):
                continue
            for candidate in module.get("candidate_topics") or []:
                if not isinstance(candidate, dict):
                    continue
                candidate_title_key = _topic_title_key(str(candidate.get("title") or ""))
                candidate_candidate_id = str(candidate.get("candidate_id") or "").strip()
                if candidate_id:
                    if candidate_candidate_id != candidate_id:
                        continue
                elif candidate_title_key != title_key:
                    continue
                candidate["status"] = status
                if notes is not None:
                    candidate["notes"] = notes
                changed = True
                break
            if changed:
                break
        if not changed:
            continue
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_path = json_path.with_suffix(".md")
        if md_path.exists():
            _sync_topic_library_markdown(payload, md_path)
        return {"json_path": str(json_path), "md_path": str(md_path)}
    return None


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
    candidate_id = str(topic.get("candidate_id") or "").strip() or None
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
            "candidate_id": candidate_id,
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
    library_status = status if status in {"approved", "used", "published", "rejected", "archived"} else "used"
    library_result = update_topic_library_candidate_status(
        base_dir=base_dir,
        account=resolved_account,
        column=str(topic.get("column") or "").strip() or None,
        title=title,
        status=library_status,
        notes=notes,
        candidate_id=candidate_id,
    )

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

    result_paths = {"ledger_path": ledger_path, "history_path": history_path}
    if library_result:
        result_paths["topic_library_json_path"] = Path(library_result["json_path"])
        result_paths["topic_library_md_path"] = Path(library_result["md_path"])
    return result_paths


def mark_topic_published_from_execution(
    *,
    date: str,
    account: str,
    title: str,
    column: str | None,
    base_dir: Path | None,
    notes: str | None = None,
    candidate_id: str | None = None,
) -> dict[str, Path]:
    root = ensure_business_directories(base_dir)
    ledger = _load_topic_usage_ledger(root)
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]
    title_key = _topic_title_key(title)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    existing = next(
        (
            entry
            for entry in entries
            if entry.get("title_key") == title_key and entry.get("account") == account
        ),
        None,
    )
    if existing is None:
        existing = {
            "title_key": title_key,
            "title": title,
            "account": account,
            "created_at": now,
            "history": [],
        }
        entries.append(existing)

    resolved_candidate_id = candidate_id or str(existing.get("candidate_id") or "").strip() or None
    resolved_column = str(column or existing.get("column") or "").strip() or None
    history = existing.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        existing["history"] = history
    history.append(
        {
            "date": date,
            "status": "published",
            "batch_path": existing.get("last_batch_path"),
            "topic_number": existing.get("last_topic_number"),
            "notes": notes,
            "timestamp": now,
        }
    )

    existing.update(
        {
            "title": title,
            "account": account,
            "column": resolved_column,
            "candidate_id": resolved_candidate_id,
            "status": "published",
            "updated_at": now,
            "notes": notes,
        }
    )

    ledger["updated_at"] = now
    ledger["entries"] = entries
    ledger_path = _save_topic_usage_ledger(root, ledger)
    library_result = update_topic_library_candidate_status(
        base_dir=base_dir,
        account=account,
        column=resolved_column,
        title=title,
        status="published",
        notes=notes,
        candidate_id=resolved_candidate_id,
    )

    month = date[:7]
    history_path = _topic_usage_history_path(root, month)
    history_lines = history_path.read_text(encoding="utf-8").splitlines() if history_path.exists() else ["# 选题使用历史", ""]
    history_lines.extend(
        [
            f"## {date}",
            f"- 标题: {title}",
            f"- 账号: {account}",
            f"- 状态: published",
            f"- 批次文件: {existing.get('last_batch_path') or '未知'}",
            f"- 题号: {existing.get('last_topic_number') or '未知'}",
            f"- 备注: {notes or '无'}",
            "",
        ]
    )
    history_path.write_text("\n".join(history_lines), encoding="utf-8")

    result_paths = {"ledger_path": ledger_path, "history_path": history_path}
    if library_result:
        result_paths["topic_library_json_path"] = Path(library_result["json_path"])
        result_paths["topic_library_md_path"] = Path(library_result["md_path"])
    return result_paths


def _latest_topic_library_paths(*, root: Path, account: str) -> list[Path]:
    library_dir = root / "topic_libraries"
    if not library_dir.exists():
        return []
    latest_by_column: dict[str, Path] = {}
    pattern = f"*_{_slugify(account)}_*.json"
    for path in sorted(library_dir.glob(pattern), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        column = str(payload.get("column") or "").strip()
        if not column or column in latest_by_column:
            continue
        latest_by_column[column] = path
    return list(latest_by_column.values())


def _collect_topic_library_dashboard_rows(*, account: str, base_dir: Path | None) -> list[dict[str, object]]:
    root = ensure_business_directories(base_dir)
    usage_ledger = _load_topic_usage_ledger(root)
    usage_by_column: dict[str, dict[str, object]] = {}
    for entry in usage_ledger.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("account") or "") != account:
            continue
        column = str(entry.get("column") or "未归类")
        bucket = usage_by_column.setdefault(column, {"approved": 0, "used": 0, "published": 0, "other": 0, "entries": []})
        status = str(entry.get("status") or "other")
        if status in {"approved", "used", "published"}:
            bucket[status] += 1
        else:
            bucket["other"] += 1
        bucket["entries"].append(entry)

    rows: list[dict[str, object]] = []
    for path in _latest_topic_library_paths(root=root, account=account):
        payload = json.loads(path.read_text(encoding="utf-8"))
        column = str(payload.get("column") or "").strip()
        lifecycle = get_column_lifecycle(account=account, column=column, base_dir=base_dir)
        lifecycle_state = str(lifecycle.get("state") or "no_record(default_generate)") if lifecycle else "no_record(default_generate)"
        lifecycle_role = str((lifecycle.get("attributes") or {}).get("role") or "") if lifecycle else ""
        counts = {"unused": 0, "approved": 0, "used": 0, "published": 0, "rejected": 0, "archived": 0}
        modules: list[dict[str, object]] = []
        for module in payload.get("modules") or []:
            if not isinstance(module, dict):
                continue
            module_counts = {"unused": 0, "approved": 0, "used": 0, "published": 0, "rejected": 0, "archived": 0}
            for candidate in module.get("candidate_topics") or []:
                if not isinstance(candidate, dict):
                    continue
                status = str(candidate.get("status") or "unused")
                module_counts[status] = module_counts.get(status, 0) + 1
                counts[status] = counts.get(status, 0) + 1
            modules.append(
                {
                    "name": module.get("name"),
                    "status": module.get("status"),
                    "counts": module_counts,
                    "sample_unused": next((c.get("title") for c in module.get("candidate_topics") or [] if isinstance(c, dict) and c.get("status") == "unused"), None),
                }
            )
        usage_summary = usage_by_column.get(column, {"approved": 0, "used": 0, "published": 0, "other": 0, "entries": []})
        published_titles = []
        published_seen: set[str] = set()
        for topic in payload.get("existing_topics") or []:
            title = ""
            tag = "历史文章"
            if isinstance(topic, dict):
                title = str(topic.get("title") or "").strip()
                tag = str(topic.get("module") or topic.get("tag") or "历史文章").strip() or "历史文章"
            else:
                title = str(topic or "").strip()
            if not title or title in published_seen:
                continue
            published_seen.add(title)
            published_titles.append({"title": title, "tag": tag})
        for entry in usage_summary.get("entries", []):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("status") or "") != "published":
                continue
            entry_title = str(entry.get("title") or "").strip()
            if not entry_title or entry_title in published_seen:
                continue
            published_seen.add(entry_title)
            published_titles.append({
                "title": entry_title,
                "tag": entry.get("candidate_id") or entry.get("role") or "published",
            })
        pending_titles = []
        for module in payload.get("modules") or []:
            if not isinstance(module, dict):
                continue
            module_name = str(module.get("name") or module.get("module") or "未分组")
            for candidate in module.get("candidate_topics") or []:
                if not isinstance(candidate, dict):
                    continue
                candidate_status = str(candidate.get("status") or "unused")
                if candidate_status in {"published", "archived", "rejected"}:
                    continue
                pending_titles.append({
                    "title": candidate.get("title"),
                    "tag": module_name,
                    "status": candidate_status,
                })
        next_priorities = [m["name"] for m in modules if m["counts"].get("unused", 0) > 0][:3]
        rows.append(
            {
                "column": column,
                "lifecycle": lifecycle_state,
                "role": lifecycle_role,
                "library_strategy": payload.get("library_strategy"),
                "existing_topics_count": len(payload.get("existing_topics") or []),
                "module_count": len(modules),
                "candidate_counts": counts,
                "usage_summary": usage_summary,
                "modules": modules,
                "next_priorities": next_priorities,
                "topic_library_path": str(path),
                "published_count": len(published_titles),
                "pending_count": len(pending_titles),
                "published_titles": published_titles,
                "pending_titles": pending_titles,
            }
        )
    rows.sort(key=lambda item: (str(item.get("lifecycle") or ""), str(item.get("column") or "")))
    return rows


def build_topic_library_dashboard(*, account: str, base_dir: Path | None, output_path: Path | None = None, action_config: dict[str, object] | None = None) -> Path:
    rows = _collect_topic_library_dashboard_rows(account=account, base_dir=base_dir)
    if not rows:
        raise ValueError("no topic libraries found for dashboard")

    active_rows = [row for row in rows if row.get("lifecycle") != "deprecated"]
    summary = {
        "total_columns": len(rows),
        "active_columns": len(active_rows),
        "deprecated_columns": len([row for row in rows if row.get("lifecycle") == "deprecated"]),
        "total_unused": sum(int((row.get("candidate_counts") or {}).get("unused", 0)) for row in rows),
        "total_published": sum(int(row.get("published_count") or 0) for row in rows),
    }

    dashboard_path = output_path or ((base_dir / "docs" / "specs" / "topic-library-dashboard.html") if base_dir else (DATA_DIR.parent / "docs" / "specs" / "topic-library-dashboard.html"))
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps({"generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z", "account": account, "summary": summary, "rows": rows, "actions": action_config or {}}, ensure_ascii=False)
    html_template = """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>__ACCOUNT_TITLE__ - 专栏概览</title>
  <style>
    :root { --bg:#0b1020; --panel:#121933; --muted:#94a3b8; --text:#e5e7eb; --green:#22c55e; --yellow:#f59e0b; --red:#ef4444; --blue:#38bdf8; }
    body { margin:0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:var(--bg); color:var(--text); }
    .wrap { max-width: 1280px; margin:0 auto; padding:24px; }
    h1 { margin:0 0 8px; }
    .meta { color:var(--muted); margin-bottom:18px; }
    .summary { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:18px; }
    .pill { background:#111827; border:1px solid #25304a; border-radius:999px; padding:8px 12px; color:#cbd5e1; }
    .toolbar { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:18px; align-items:center; }
    input, select, button { background:#0f172a; color:var(--text); border:1px solid #334155; border-radius:10px; padding:10px 12px; }
    button { cursor:pointer; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(300px,1fr)); gap:16px; }
    .card { background:var(--panel); border:1px solid #24304f; border-radius:16px; padding:16px; box-shadow:0 8px 24px rgba(0,0,0,.25); }
    .card h2 { margin:0 0 10px; font-size:18px; }
    .row { display:flex; gap:10px; flex-wrap:wrap; margin:8px 0 12px; }
    .tag { display:inline-block; border-radius:999px; padding:2px 8px; font-size:12px; background:#1e293b; margin-right:6px; margin-bottom:6px; }
    .state-active_revenue { background: rgba(34,197,94,.15); color:#86efac; }
    .state-active_traffic { background: rgba(56,189,248,.15); color:#7dd3fc; }
    .state-paused { background: rgba(245,158,11,.15); color:#fcd34d; }
    .state-deprecated { background: rgba(239,68,68,.15); color:#fca5a5; }
    .state-incubating, .state-no_record-default_generate { background: rgba(148,163,184,.15); color:#cbd5e1; }
    .count { font-weight:700; }
    details { margin-top:10px; }
    summary { cursor:pointer; color:#cbd5e1; }
    ul { margin:8px 0 0 18px; padding:0; }
    li { margin:6px 0; }
    .subtle { color:var(--muted); font-size:12px; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>__ACCOUNT_TITLE__ 专栏概览</h1>
    <div class=\"meta\">你要的简化版：概要看所有专栏，点开看已发布题目和待发布题目（带板块 tag）。不做校准时，系统沿用当前 baseline，并按每次发布/同步动作更新题库状态；点击校准 baseline 才会按当前发布实况重建 baseline。</div>
    <div class=\"summary\">
      <div class=\"pill\">总专栏数：<strong id=\"sum-total\"></strong></div>
      <div class=\"pill\">待发布总量：<strong id=\"sum-pending\"></strong></div>
      <div class=\"pill\">已发布总量：<strong id=\"sum-published\"></strong></div>
    </div>
    <div class=\"toolbar\">
      <input id=\"search\" placeholder=\"搜索专栏或题目\" />
      <select id=\"lifecycle-filter\">
        <option value=\"all\">全部状态</option>
        <option value=\"active_revenue\">active_revenue</option>
        <option value=\"active_traffic\">active_traffic</option>
        <option value=\"paused\">paused</option>
        <option value=\"incubating\">incubating</option>
        <option value=\"no_record(default_generate)\">no_record(default_generate)</option>
      </select>
      <button id=\"calibrate-btn\" type=\"button\">校准 baseline</button>
      <span id=\"action-status\" class=\"subtle\"></span>
    </div>
    <div id=\"grid\" class=\"grid\"></div>
  </div>
<script>
const DATA = __DATA_JSON__;
const ACTIONS = DATA.actions || {};
const gridEl = document.getElementById('grid');
const searchEl = document.getElementById('search');
const lifecycleEl = document.getElementById('lifecycle-filter');
const calibrateBtn = document.getElementById('calibrate-btn');
const actionStatusEl = document.getElementById('action-status');
function cssLifecycle(value) {
  return String(value || '').replace(/[^a-zA-Z0-9_-]/g, '-');
}
function matches(row) {
  const q = searchEl.value.trim().toLowerCase();
  const lf = lifecycleEl.value;
  if (lf !== 'all' && row.lifecycle !== lf) return false;
  if (!q) return true;
  const hay = [row.column, row.lifecycle]
    .concat((row.published_titles||[]).map(x => x.title || ''))
    .concat((row.pending_titles||[]).map(x => x.title || ''))
    .join(' ')
    .toLowerCase();
  return hay.includes(q);
}
function renderSummary(rows) {
  document.getElementById('sum-total').textContent = rows.length;
  document.getElementById('sum-pending').textContent = rows.reduce((n, row) => n + (row.pending_titles||[]).length, 0);
  document.getElementById('sum-published').textContent = rows.reduce((n, row) => n + (row.published_titles||[]).length, 0);
}
function render() {
  const rows = DATA.rows.filter(matches);
  renderSummary(rows);
  gridEl.innerHTML = rows.map(row => `
    <div class=\"card\">
      <h2>${row.column}</h2>
      <div class=\"row\">
        <span class=\"tag state-${cssLifecycle(row.lifecycle)}\">${row.lifecycle}</span>
        ${row.role ? `<span class=\"tag\">${row.role}</span>` : ''}
      </div>
      <div class=\"row\">\n        <span>已发布：<span class=\"count\">${row.published_count ?? (row.published_titles||[]).length}</span></span>\n        <span>待发布：<span class=\"count\">${row.pending_count ?? (row.pending_titles||[]).length}</span></span>\n      </div>
      <details>
        <summary>查看已发布文章题目</summary>
        <ul>
          ${(row.published_titles||[]).length ? (row.published_titles||[]).map(item => `<li>${item.title} ${item.tag ? `<span class=\"tag\">${item.tag}</span>` : ''}</li>`).join('') : '<li class=\"subtle\">暂无</li>'}
        </ul>
      </details>
      <details>
        <summary>查看待发布文章题目</summary>
        <ul>
          ${(row.pending_titles||[]).length ? (row.pending_titles||[]).map(item => `<li>${item.title} <span class=\"tag\">${item.tag || '未分组'}</span> <span class=\"tag\">${item.status}</span></li>`).join('') : '<li class=\"subtle\">暂无</li>'}
        </ul>
      </details>
    </div>
  `).join('');
}
function setupActions() {
  calibrateBtn.textContent = ACTIONS.calibrate_label || '校准 baseline';
  if (!ACTIONS.can_calibrate || !ACTIONS.calibrate_path) {
    calibrateBtn.disabled = true;
    actionStatusEl.textContent = ACTIONS.disabled_reason || '当前页面未配置校准动作';
    return;
  }
  if (ACTIONS.status_message) {
    actionStatusEl.textContent = ACTIONS.status_message;
  }
  calibrateBtn.addEventListener('click', async () => {
    calibrateBtn.disabled = true;
    actionStatusEl.textContent = '正在根据当前发布实况校准 baseline，请稍候…';
    try {
      const resp = await fetch(ACTIONS.calibrate_path, { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        throw new Error((data && (data.error || data.message)) || `HTTP ${resp.status}`);
      }
      actionStatusEl.textContent = data.message || '校准完成，正在刷新页面…';
      window.location.reload();
    } catch (err) {
      actionStatusEl.textContent = `校准失败：${err.message || err}`;
      calibrateBtn.disabled = false;
    }
  });
}
searchEl.addEventListener('input', render);
lifecycleEl.addEventListener('change', render);
setupActions();
render();
</script>
</body>
</html>"""
    html = html_template.replace("__ACCOUNT_TITLE__", escape(account)).replace("__DATA_JSON__", data_json)
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path


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
        topic.setdefault("candidate_id", None)
        topic.setdefault("topic_source", "manual")
        topic.setdefault("topic_module", None)
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
