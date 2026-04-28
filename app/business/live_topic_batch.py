from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.business.ops import is_topic_used, write_topic_batch_files
from app.state import get_column_lifecycle


ColumnScore = dict[str, object]


def _recent_titles(snapshot: dict[str, Any]) -> list[str]:
    titles = snapshot.get("article_titles")
    if not isinstance(titles, list):
        return []
    return [str(item).strip() for item in titles if str(item).strip()]


def _column_names(snapshot: dict[str, Any]) -> list[str]:
    names = snapshot.get("column_names")
    if not isinstance(names, list):
        return []
    return [str(item).strip() for item in names if str(item).strip()]


def _detect_cluster(titles: list[str]) -> tuple[str, dict[str, int]]:
    joined = "\n".join(titles)
    scores = {
        "dify": sum(token in joined for token in ["Dify", "RAG", "知识库", "工作流", "插件"]),
        "local_ai": sum(token in joined for token in ["Ollama", "OpenWebUI", "vLLM", "RAG", "Agent"]),
        "python": sum(token in joined for token in ["Python", "OCR", "Playwright"]),
        "godot": sum(token in joined for token in ["Godot", "安卓", "APK"]),
    }
    cluster = max(scores, key=scores.get) if scores else "generic"
    if scores.get(cluster, 0) == 0:
        cluster = "generic"
    return cluster, scores


def _pick_column(snapshot: dict[str, Any], cluster: str) -> str:
    names = _column_names(snapshot)
    if cluster == "dify":
        for name in names:
            if "Dify" in name:
                return name
        return "AI实践-Dify专栏"
    if cluster == "local_ai":
        for name in names:
            if any(token in name for token in ["AI", "工坊", "实战笔记"]):
                return name
        return names[0] if names else "生成式AI实战笔记"
    if cluster == "python":
        for name in names:
            if "Python" in name:
                return name
        return names[0] if names else "Python职场加速器：实战技巧与高效工具集"
    return names[0] if names else "未识别栏目"


def _pick_secondary_column(snapshot: dict[str, Any], primary_column: str) -> str | None:
    names = [name for name in _column_names(snapshot) if name != primary_column]
    if not names:
        return None

    preferred_tokens = (
        "企业级AI落地",
        "应用系统",
        "技术前沿每日速读",
        "AI",
        "Python",
    )
    for token in preferred_tokens:
        for name in names:
            if token in name:
                return name
    return names[0]


def _guess_full_capture_path(snapshot_path: Path) -> Path | None:
    if not snapshot_path.name.endswith("_live.json"):
        return None
    candidate = snapshot_path.with_name(snapshot_path.name.replace("_live.json", "_full.json"))
    return candidate if candidate.exists() else None


def _load_full_capture(snapshot_path: Path) -> dict[str, Any] | None:
    candidate = _guess_full_capture_path(snapshot_path)
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _column_complementarity_score(title: str, primary_column: str) -> float:
    if title == primary_column:
        return -999.0
    score = 0.0
    if ("企业级AI落地" in title or "应用系统" in title) and "Dify" in primary_column:
        score += 4.0
    if "技术前沿每日速读" in title:
        score += 3.0
    if "Python" in title and "Dify" in primary_column:
        score += 2.0
    if "电脑疑难" in title or "Godot" in title:
        score -= 3.0
    return score


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


def _latest_files(path: Path, limit: int = 10) -> list[Path]:
    if not path.exists():
        return []
    files = [item for item in path.iterdir() if item.is_file()]
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[:limit]


def _read_signal_text(path: Path) -> str:
    try:
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            return json.dumps(payload, ensure_ascii=False)
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _business_signal_bonus(*, base_dir: Path | None, account: str, column_title: str) -> tuple[float, list[str], list[str]]:
    if base_dir is None:
        return 0.0, [], []

    account_slug = _slugify(account)
    score = 0.0
    reasons: list[str] = []
    source_signals: list[str] = []

    lifecycle = get_column_lifecycle(account=account, column=column_title, base_dir=base_dir)
    if lifecycle:
        lifecycle_state = str(lifecycle.get("state") or "").strip()
        lifecycle_role = str((lifecycle.get("attributes") or {}).get("role") or "").strip()
        if lifecycle_state == "paused":
            score -= 6.0
            reasons.append("专栏生命周期状态为 paused，当前不应优先承接当天第二篇")
            source_signals.append("lifecycle: paused")
        elif lifecycle_state == "deprecated":
            score -= 12.0
            reasons.append("专栏生命周期状态为 deprecated，应停止常规更新")
            source_signals.append("lifecycle: deprecated")
        elif lifecycle_state == "active_traffic":
            score += 2.0
            reasons.append("专栏生命周期状态为 active_traffic，适合承担引流位")
            source_signals.append("lifecycle: active_traffic")
        elif lifecycle_state == "active_revenue":
            score += 2.5
            reasons.append("专栏生命周期状态为 active_revenue，适合承担收益位")
            source_signals.append("lifecycle: active_revenue")
        elif lifecycle_state == "incubating":
            score += 0.5
            reasons.append("专栏处于 incubating，可少量试投但需要控制节奏")
            source_signals.append("lifecycle: incubating")
        if lifecycle_role:
            reasons.append(f"生命周期记录角色为 {lifecycle_role}")
            source_signals.append(f"lifecycle role: {lifecycle_role}")

    business_root = base_dir / "data" / "business"
    intel_root = base_dir / "data" / "intel"

    strategy_files = [path for path in _latest_files(business_root / "strategy_outputs", limit=10) if account_slug in path.stem][:3]
    column_files = [path for path in _latest_files(business_root / "columns", limit=10) if account_slug in path.stem][:5]
    sales_files = _latest_files(intel_root / "sales", limit=5)
    feedback_files = _latest_files(intel_root / "feedback", limit=5)

    for path in strategy_files:
        text = _read_signal_text(path)
        if column_title in text:
            score += 2.0
            reasons.append("最新策略输出直接提到该专栏，可视为当前经营重点之一")
            source_signals.append(f"strategy match: {path.name}")
            break

    for path in column_files:
        text = _read_signal_text(path)
        if column_title in text:
            score += 2.5
            reasons.append("存在该专栏的资产/空缺图，说明后续可沿缺口继续补位")
            source_signals.append(f"column asset match: {path.name}")
            if any(token in text for token in ["空缺", "gap", "转化", "点击"]):
                score += 1.0
                reasons.append("专栏资产里能看到空缺或转化相关信号，适合承接第二篇")
            break

    for path in sales_files:
        text = _read_signal_text(path)
        if column_title in text:
            score += 2.5
            reasons.append("近期 sales/click 记录直接命中该专栏，可作为收益潜力信号")
            source_signals.append(f"sales match: {path.name}")
            break

    for path in feedback_files:
        text = _read_signal_text(path)
        if column_title in text:
            score += 1.5
            reasons.append("近期反馈里直接出现该专栏，说明用户或市场对它有关注信号")
            source_signals.append(f"feedback match: {path.name}")
            break

    return score, reasons, source_signals


def _score_secondary_columns(full_capture: dict[str, Any] | None, snapshot: dict[str, Any], primary_column: str) -> list[ColumnScore]:
    raw_columns = full_capture.get("columns") if isinstance(full_capture, dict) else None
    columns = [item for item in (raw_columns or []) if isinstance(item, dict) and str(item.get("title") or "").strip()]
    if not columns:
        columns = [{"title": name} for name in _column_names(snapshot)]

    scores: list[ColumnScore] = []
    for column in columns:
        title = str(column.get("title") or "").strip()
        if not title or title == primary_column:
            continue

        score = 0.0
        reasons: list[str] = []

        complementarity = _column_complementarity_score(title, primary_column)
        score += complementarity
        if complementarity > 0:
            reasons.append("与旗舰专栏形成互补，可作为第二收益点")
        elif complementarity < 0:
            reasons.append("与当前旗舰主线互补性较弱")

        price = float(column.get("price") or 0)
        if price > 0:
            score += 3.0
            reasons.append(f"付费专栏（price={price}）有直接收益潜力")
        else:
            score += 1.0
            reasons.append("免费/未定价专栏更偏引流承接")

        article_count = int(column.get("article_count") or 0)
        if article_count >= 8:
            score += 2.0
            reasons.append(f"历史文章数较多（{article_count}），基础活跃度更稳")
        elif article_count > 0:
            score += 1.0
            reasons.append(f"已有一定存量（{article_count} 篇）可承接")
        else:
            reasons.append("存量较少，活跃度需要谨慎")

        metric_2 = int(column.get("metric_2") or 0)
        if metric_2 > 0:
            score += 1.5
            reasons.append(f"附加互动/指标值为 {metric_2}，说明有一定反馈信号")

        status = str(column.get("status") or "").strip()
        if status == "已上架":
            score += 1.0
            reasons.append("当前状态已上架，可直接承接第二篇")
        elif status:
            score -= 1.0
            reasons.append(f"状态为 {status}，可用性较弱")

        scores.append(
            {
                "title": title,
                "score": round(score, 2),
                "reasons": reasons,
                "price": price,
                "article_count": article_count,
                "metric_2": metric_2,
                "status": status,
            }
        )

    scores.sort(key=lambda item: (float(item["score"]), float(item.get("price") or 0), int(item.get("article_count") or 0)), reverse=True)
    return scores


def _score_secondary_columns_with_business_signals(
    *,
    full_capture: dict[str, Any] | None,
    snapshot: dict[str, Any],
    primary_column: str,
    base_dir: Path | None,
    account: str,
) -> list[ColumnScore]:
    scores = _score_secondary_columns(full_capture, snapshot, primary_column)
    for item in scores:
        bonus, reasons, source_signals = _business_signal_bonus(
            base_dir=base_dir,
            account=account,
            column_title=str(item["title"]),
        )
        if bonus:
            item["score"] = round(float(item["score"]) + bonus, 2)
            item.setdefault("reasons", []).extend(reasons)
            item["business_signal_bonus"] = round(bonus, 2)
            item["business_signal_sources"] = source_signals
    scores.sort(key=lambda item: (float(item["score"]), float(item.get("price") or 0), int(item.get("article_count") or 0)), reverse=True)
    return scores


def _pick_secondary_column_with_score(
    snapshot: dict[str, Any],
    snapshot_path: Path,
    primary_column: str,
    *,
    base_dir: Path | None,
    account: str,
) -> tuple[str | None, list[ColumnScore]]:
    full_capture = _load_full_capture(snapshot_path)
    scored = _score_secondary_columns_with_business_signals(
        full_capture=full_capture,
        snapshot=snapshot,
        primary_column=primary_column,
        base_dir=base_dir,
        account=account,
    )
    if scored:
        return str(scored[0]["title"]), scored
    fallback = _pick_secondary_column(snapshot, primary_column)
    return fallback, scored


def _templates_for_cluster(cluster: str, column: str, account: str) -> list[dict[str, str]]:
    if cluster == "dify":
        return [
            {"title": "[Dify实战] 多轮对话状态管理：上下文保持与槽位填充", "role": "信任题", "priority": "主推", "angle": "状态管理"},
            {"title": "[Dify实战] 长文档智能摘要：多层级提炼与关键信息抽取", "role": "信任题", "priority": "主推", "angle": "长文档摘要"},
            {"title": "[RAG实战] Dify 多日期提问召回不全？一次彻底解决“检索被稀释”的工程方案（含完整实现思路）", "role": "转化题", "priority": "主推", "angle": "检索稀释修复"},
            {"title": "[Dify实战] 工作流调试总卡在中间节点？一套可复用的排查 checklist", "role": "引流题", "priority": "主推", "angle": "工作流调试"},
            {"title": "[Dify实战] 知识库版本更新策略：如何避免“内容改了，答案还是旧的”", "role": "信任题", "priority": "主推", "angle": "知识更新"},
            {"title": "[Dify实战] 从业务案例到可复用模板：怎样把一次项目沉淀成长期资产", "role": "转化题", "priority": "主推", "angle": "模板资产化"},
            {"title": "[Dify实战] 多应用协作怎么设计？从单点助手到系统化 AI 工具箱", "role": "信任题", "priority": "备用", "angle": "多应用协作"},
            {"title": "[Dify实战] 做完业务助手后，下一步该补什么？Dify 项目进阶路线图", "role": "引流题", "priority": "备用", "angle": "进阶路线图"},
            {"title": "[Dify实战] Prompt、知识库、工作流到底谁该负责什么？一篇讲清边界", "role": "引流题", "priority": "备用", "angle": "能力边界"},
        ]
    if cluster == "local_ai":
        return [
            {"title": "【AI】vLLM + OpenWebUI 组合部署：高吞吐推理与界面一体化实战", "role": "信任题", "priority": "主推", "angle": "高吞吐部署"},
            {"title": "【AI】本地RAG选型：Chroma、Milvus、Weaviate、PGVector 深度对比", "role": "信任题", "priority": "主推", "angle": "RAG 选型"},
            {"title": "【AI】Ollama + FastAPI 搭建企业内网统一推理网关", "role": "转化题", "priority": "主推", "angle": "推理网关"},
            {"title": "【AI】RAG 提示词模板优化：分步检索、重排序与上下文压缩", "role": "引流题", "priority": "主推", "angle": "提示词优化"},
            {"title": "【AI】日志与监控：Prometheus + Grafana 监控本地 LLM 指标", "role": "信任题", "priority": "主推", "angle": "监控体系"},
            {"title": "【AI】模型推理成本优化：批处理、动态批次与缓存复用", "role": "转化题", "priority": "主推", "angle": "成本优化"},
            {"title": "【AI】多模型路由：基于成本/延迟/质量的智能选择", "role": "备用题", "priority": "备用", "angle": "多模型路由"},
            {"title": "【AI】本地 Agent 调度：任务优先级、回退与人类介入", "role": "备用题", "priority": "备用", "angle": "Agent 调度"},
        ]
    return [
        {"title": f"[{account}] 基于真实账号数据的下一阶段选题拆解与延续策略", "role": "引流题", "priority": "主推", "angle": "延续策略"},
        {"title": f"[{account}] 从最近已发内容里，哪些主题值得继续深挖？", "role": "信任题", "priority": "主推", "angle": "主题延展"},
        {"title": f"[{account}] 如何把已有文章串成一个更清晰的栏目主线", "role": "信任题", "priority": "主推", "angle": "栏目主线"},
        {"title": f"[{account}] 什么样的后续题最容易承接已有读者兴趣？", "role": "转化题", "priority": "主推", "angle": "兴趣承接"},
        {"title": f"[{account}] 从真实已发标题看，当前内容结构缺了哪一块", "role": "引流题", "priority": "主推", "angle": "缺口分析"},
        {"title": f"[{account}] 如何基于真实发布结果更新下一轮选题优先级", "role": "转化题", "priority": "主推", "angle": "优先级调整"},
        {"title": f"[{account}] 一周内容复盘：哪些题值得升级成系列", "role": "备用题", "priority": "备用", "angle": "系列升级"},
        {"title": f"[{account}] 真实内容资产盘点：下一步该补方法题还是案例题", "role": "备用题", "priority": "备用", "angle": "资产盘点"},
    ]


def _secondary_templates_for_column(column: str) -> list[dict[str, str]]:
    if "企业级AI落地" in column or "应用系统" in column:
        return [
            {"title": "[企业AI落地] 为什么很多内网 AI 项目卡在“能跑”之后？这 4 个工程缺口最常见", "role": "转化题", "priority": "主推", "angle": "工程缺口"},
            {"title": "[企业AI落地] 模型部署只是开始：企业 AI 系统真正难的是哪三段工程链路？", "role": "信任题", "priority": "主推", "angle": "工程链路"},
            {"title": "[AI架构] 从单点 Demo 到生产级平台：企业 AI 应用系统为什么总卡在中间层", "role": "信任题", "priority": "备用", "angle": "平台中间层"},
        ]
    if "技术前沿每日速读" in column:
        return [
            {"title": "[AI] 今天大家都在做企业助手，为什么“流程闭环”比“模型更强”更重要？", "role": "引流题", "priority": "主推", "angle": "流程闭环"},
            {"title": "[AI] 这周最值得关注的 3 个 Dify / 企业AI 落地变化：看懂再决定要不要跟进", "role": "引流题", "priority": "主推", "angle": "热点速读"},
            {"title": "[AI] 企业知识库项目为什么总是“看起来快成了”，结果迟迟落不了地？", "role": "信任题", "priority": "备用", "angle": "落地卡点"},
        ]
    if "Python" in column:
        return [
            {"title": "[Python] 自动化脚本写得快，为什么一上线就容易崩？从可用到可维护差在哪", "role": "引流题", "priority": "主推", "angle": "可维护性"},
            {"title": "[Python实战] 批量处理业务文本时，怎样把脚本升级成可复用的小工具", "role": "信任题", "priority": "主推", "angle": "脚本升级"},
        ]
    return [
        {"title": f"[{column}] 为什么这个专栏适合承担当天第二篇：从活跃度到收益点的实际考虑", "role": "引流题", "priority": "主推", "angle": "第二专栏激活"},
        {"title": f"[{column}] 做第二篇补位内容时，怎样避免和旗舰专栏撞题？", "role": "信任题", "priority": "备用", "angle": "补位防撞题"},
    ]


def plan_topic_batch_from_live(*, date: str, account: str, snapshot_path: Path, base_dir: Path | None) -> dict[str, Path]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    recent_titles = _recent_titles(snapshot)
    if not recent_titles:
        raise ValueError("live snapshot does not contain article_titles; formal topic planning requires real account facts")

    cluster, scores = _detect_cluster(recent_titles)
    primary_column = _pick_column(snapshot, cluster)
    secondary_column, secondary_column_scores = _pick_secondary_column_with_score(
        snapshot,
        snapshot_path,
        primary_column,
        base_dir=base_dir,
        account=account,
    )
    primary_candidates = _templates_for_cluster(cluster, primary_column, account)
    secondary_candidates = _secondary_templates_for_column(secondary_column) if secondary_column else []
    recent_title_set = {title.strip() for title in recent_titles}

    topics: list[dict[str, object]] = []

    def _append_candidate(candidate: dict[str, str], topic_column: str, *, split_reason: str) -> None:
        title = candidate["title"]
        if title in recent_title_set:
            return
        if is_topic_used(title=title, base_dir=base_dir, account=account):
            return
        number = len(topics) + 1
        topics.append(
            {
                "number": number,
                "title": title,
                "audience": f"关注{topic_column}并希望继续看同一主线内容的读者",
                "account": account,
                "column": topic_column,
                "reason": f"基于 live snapshot 中最近已发标题聚类到 {cluster} 主线后，按延续/补缺口原则生成。{split_reason}",
                "expected_value": f"与当前账号真实内容主线保持连续，避免跳题，同时补上 {candidate['angle']} 这一缺口。",
                "why_now": f"当天正式选题应优先建立在账号实时采集事实之上；当前最近标题集中在 {cluster} 相关主题。",
                "cta": "如果你认可这个方向，我可以继续把它扩成当天发文包和正文初稿。",
                "role": "转化题" if candidate["role"] == "转化题" else ("信任题" if candidate["role"] == "信任题" else "引流题"),
                "risk": "若账号实时页面样本过少，需补一次更完整采集再确认优先级。",
                "priority": candidate["priority"],
            }
        )

    if primary_candidates:
        _append_candidate(
            primary_candidates[0],
            primary_column,
            split_reason="作为当天旗舰主更，优先落在当前最强主线专栏。",
        )
    if secondary_candidates and secondary_column:
        _append_candidate(
            secondary_candidates[0],
            secondary_column,
            split_reason="按照该账号日更两篇尽量分属不同专栏的经营原则，把第二篇放到次级收益点专栏以保持多专栏活性。",
        )

    for candidate in primary_candidates[1:]:
        _append_candidate(candidate, primary_column, split_reason="继续补齐旗舰主线专栏的连续缺口。")
        if len(topics) == 8:
            break
    if len(topics) < 8 and secondary_candidates and secondary_column:
        for candidate in secondary_candidates[1:]:
            _append_candidate(candidate, secondary_column, split_reason="作为第二专栏的补位候选，用于维持多专栏活性。")
            if len(topics) == 8:
                break

    if len(topics) < 8:
        raise ValueError("not enough non-duplicate live-based topic candidates; collect a fuller account snapshot first")

    batch = {
        "account": account,
        "generated_at": str(snapshot.get("captured_at") or f"{date}T10:00:00Z"),
        "batch_strategy": f"Strictly fact-based topic batch derived from live snapshot for {account}; dominant cluster={cluster}.",
        "writing_order": [topic["title"] for topic in topics[:6]],
        "topics": topics,
        "changes_from_previous": [
            "This batch was generated only after loading a live account snapshot.",
            "Recent live titles were treated as hard anti-duplication references before proposing new topics.",
            "For 技术小甜甜 daily planning, the first two publish slots now prefer different columns when a viable secondary column is visible in live facts.",
        ],
        "source_signals": [
            f"live snapshot: {snapshot_path}",
            f"live article count: {len(recent_titles)}",
            f"detected columns: {', '.join(_column_names(snapshot)[:5]) or 'unknown'}",
            f"dominant cluster: {cluster} -> {scores}",
        ],
        "notes": "Formal topic planning should fail closed without same-day live account facts.",
    }
    if secondary_column_scores:
        top_secondary = secondary_column_scores[0]
        signal_parts = [
            f"selected={top_secondary['title']}",
            f"score={top_secondary['score']}",
            f"reasons={'; '.join(top_secondary['reasons'])}",
        ]
        if top_secondary.get("business_signal_sources"):
            signal_parts.append(f"sources={', '.join(top_secondary['business_signal_sources'])}")
        batch["source_signals"].append("secondary column scorer: " + " ".join(signal_parts))
    return write_topic_batch_files(batch=batch, date=date, base_dir=base_dir)
