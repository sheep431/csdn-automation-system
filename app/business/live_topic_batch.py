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
    if candidate.exists():
        return candidate

    snapshot_name = snapshot_path.stem
    account = snapshot_name.split("_", 1)[1].replace("_live", "") if "_" in snapshot_name else ""
    if not account:
        return None

    siblings = sorted(snapshot_path.parent.glob(f"*_{account}_full.json"), reverse=True)
    return siblings[0] if siblings else None


def _load_full_capture(snapshot_path: Path) -> dict[str, Any] | None:
    candidate = _guess_full_capture_path(snapshot_path)
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    payload.setdefault("_resolved_full_capture_path", str(candidate))
    return payload

def _column_complementarity_score(title: str, primary_column: str) -> float:
    if title == primary_column:
        return -999.0
    score = 0.0
    if ("企业级AI落地" in title or "应用系统" in title) and "Dify" in primary_column:
        score += 4.0
    if "技术前沿每日速读" in title:
        score += 3.0
    if "Python" in title and "Dify" in primary_column:
        score -= 1.5
    if "电脑疑难" in title or "Godot" in title or "ComfyUI" in title:
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

        topical_title = title.lower()
        if "dify" in primary_column.lower():
            if any(token in topical_title for token in ["ai", "dify", "python", "技术前沿"]):
                score += 1.0
                reasons.append("与当前 AI / Dify 主线仍存在主题相关性")
            else:
                score -= 6.0
                reasons.append("栏目标题与当前 AI / Dify 主线关联弱，不适合作为今天第二篇")

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


def _title_key(title: str) -> str:
    cleaned = []
    for ch in str(title).strip().lower():
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            cleaned.append(ch)
    return "".join(cleaned)


def _load_topic_usage_titles(*, base_dir: Path | None, account: str) -> list[str]:
    if base_dir is None:
        return []
    ledger_path = base_dir / "data" / "business" / "topic_usage" / "topic_usage_ledger.json"
    if not ledger_path.exists():
        return []
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    titles: list[str] = []
    for entry in ledger.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("account") or "") != account:
            continue
        title = str(entry.get("title") or "").strip()
        if title:
            titles.append(title)
    return titles


def _collect_historical_titles(*, snapshot: dict[str, Any], full_capture: dict[str, Any] | None, base_dir: Path | None, account: str) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        key = _title_key(text)
        if not key or key in seen:
            return
        seen.add(key)
        titles.append(text)

    for title in _recent_titles(snapshot):
        add(title)

    if isinstance(full_capture, dict):
        for column in full_capture.get("columns") or []:
            if not isinstance(column, dict):
                continue
            for article in column.get("articles") or []:
                if not isinstance(article, dict):
                    continue
                add(str(article.get("title") or ""))

    for title in _load_topic_usage_titles(base_dir=base_dir, account=account):
        add(title)

    return titles


def _collect_signal_corpus(*, snapshot: dict[str, Any], full_capture: dict[str, Any] | None, base_dir: Path | None, account: str) -> str:
    pieces: list[str] = []
    pieces.extend(_recent_titles(snapshot))
    if isinstance(full_capture, dict):
        for column in full_capture.get("columns") or []:
            if not isinstance(column, dict):
                continue
            pieces.append(str(column.get("title") or ""))
            pieces.append(str(column.get("description") or ""))
            for article in (column.get("articles") or [])[:20]:
                if not isinstance(article, dict):
                    continue
                pieces.append(str(article.get("title") or ""))
                pieces.append(str(article.get("summary") or ""))

    if base_dir is not None:
        account_slug = _slugify(account)
        for path in _latest_files(base_dir / "data" / "business" / "strategy_outputs", limit=6):
            if account_slug in path.stem:
                pieces.append(_read_signal_text(path))
        for path in _latest_files(base_dir / "data" / "business" / "columns", limit=8):
            if account_slug in path.stem:
                pieces.append(_read_signal_text(path))
        for path in _latest_files(base_dir / "data" / "intel" / "feedback", limit=8):
            pieces.append(_read_signal_text(path))
        for path in _latest_files(base_dir / "data" / "intel" / "sales", limit=8):
            pieces.append(_read_signal_text(path))
    return "\n".join(piece for piece in pieces if piece)


def _select_focuses(cluster: str, corpus: str) -> list[str]:
    theme_definitions = {
        "dify": [
            ("企业助手", ["企业助手", "内部助手", "ai助手"]),
            ("知识库问答", ["知识库", "问答", "检索", "召回"]),
            ("工作流自动化", ["工作流", "自动化", "节点"]),
            ("智能体", ["智能体", "agent"]),
            ("长文档处理", ["长文档", "摘要", "提炼", "文档"]),
            ("评审审批", ["评审", "审批", "审核"]),
            ("会议纪要", ["会议纪要"]),
            ("标书生成", ["标书", "招投标"]),
        ],
        "local_ai": [
            ("本地部署", ["本地", "部署", "内网"]),
            ("推理网关", ["推理", "网关"]),
            ("RAG系统", ["rag", "检索", "知识库"]),
            ("监控运维", ["监控", "grafana", "prometheus"]),
        ],
        "python": [
            ("自动化脚本", ["自动化", "脚本"]),
            ("环境管理", ["venv", "pip", "解释器"]),
            ("文本处理", ["文本", "批量", "解析"]),
            ("工程化", ["可维护", "工程", "上线"]),
        ],
    }
    defaults = {
        "dify": ["企业助手", "知识库问答", "工作流自动化", "智能体"],
        "local_ai": ["本地部署", "RAG系统", "推理网关"],
        "python": ["自动化脚本", "环境管理", "工程化"],
        "generic": ["真实案例", "流程闭环", "落地复盘"],
    }
    corpus_lower = corpus.lower()
    scored: list[tuple[int, str]] = []
    for label, keywords in theme_definitions.get(cluster, []):
        score = sum(corpus_lower.count(keyword.lower()) for keyword in keywords)
        scored.append((score, label))
    scored.sort(key=lambda item: item[0], reverse=True)
    focuses = [label for score, label in scored if score > 0][:4]
    for label in defaults.get(cluster, defaults["generic"]):
        if label not in focuses:
            focuses.append(label)
        if len(focuses) >= 4:
            break
    return focuses


def _generate_cluster_candidates(cluster: str, focuses: list[str], history_keys: set[str], account: str) -> list[dict[str, str]]:
    if cluster == "dify":
        patterns = [
            ("多轮状态怎么设计，才能避免越聊越乱？", "状态治理", "信任题", "主推"),
            ("知识库一更新，为什么回答还是旧的？从版本治理到回写机制一次讲清", "知识更新", "信任题", "主推"),
            ("工作流上线后总卡在中间节点？如何把排查从经验流变成固定动作", "工作流调试", "引流题", "主推"),
            ("为什么 demo 能跑，上线后却很快失控？真正缺的不是模型，而是流程闭环", "流程闭环", "转化题", "主推"),
            ("智能体什么时候该上，什么时候反而该退回普通工作流？", "智能体取舍", "引流题", "主推"),
            ("评审/审批链路接进来后，怎样避免人审节点把自动化彻底卡死", "审批闭环", "转化题", "主推"),
            ("长文档处理做了很多次，为什么结果还是不稳定？关键在这 3 层拆分", "长文档处理", "信任题", "主推"),
            ("从一次项目到长期资产，怎样把可复用节点、提示词和规则沉淀下来", "资产化沉淀", "转化题", "备用"),
            ("企业内部助手真正难的不是接模型，而是权限、状态和反馈回写怎么串起来", "权限与回写", "信任题", "备用"),
            ("效果评估总靠感觉？怎样给知识库问答建立最小可执行评估闭环", "评估闭环", "转化题", "备用"),
        ]
        candidates = []
        for focus in focuses:
            for question, angle, role, priority in patterns:
                title = f"[Dify实战] {focus} 场景里，{question}"
                key = _title_key(title)
                if key in history_keys:
                    continue
                candidates.append({"title": title, "role": role, "priority": priority, "angle": angle})
                history_keys.add(key)
        return candidates

    if cluster == "local_ai":
        patterns = [
            ("为什么很多团队把环境搭起来后，还是迟迟进不了稳定使用？", "落地稳定性", "信任题", "主推"),
            ("从单机试验到团队可用，最容易漏掉哪三段工程链路？", "工程链路", "转化题", "主推"),
            ("如果必须在成本、延迟、效果之间取舍，应该先砍哪一项？", "成本取舍", "引流题", "主推"),
            ("日志、监控、回退不补齐，为什么最终都会回到人工顶着？", "运维闭环", "信任题", "备用"),
        ]
        candidates = []
        for focus in focuses:
            for question, angle, role, priority in patterns:
                title = f"[企业AI落地] {focus} 里，{question}"
                key = _title_key(title)
                if key in history_keys:
                    continue
                candidates.append({"title": title, "role": role, "priority": priority, "angle": angle})
                history_keys.add(key)
        return candidates

    patterns = [
        ("为什么看起来只是小脚本，一上线就会暴露维护成本？", "工程化", "信任题", "主推"),
        ("从能跑到能复用，中间最值得补的抽象层到底是什么？", "复用抽象", "转化题", "主推"),
        ("如果要给新人少踩坑，只讲哪 3 个原则最值？", "避坑原则", "引流题", "主推"),
    ]
    candidates = []
    for focus in focuses:
        for question, angle, role, priority in patterns:
            title = f"[Python实战] {focus} 场景下，{question}"
            key = _title_key(title)
            if key in history_keys:
                continue
            candidates.append({"title": title, "role": role, "priority": priority, "angle": angle})
            history_keys.add(key)
    if not candidates:
        fallback_title = f"[{account}] 基于实时数据重新生成的下一轮选题复盘与缺口清单"
        if _title_key(fallback_title) not in history_keys:
            candidates.append({"title": fallback_title, "role": "信任题", "priority": "主推", "angle": "缺口复盘"})
    return candidates


def _generate_secondary_candidates(column: str, focuses: list[str], history_keys: set[str]) -> list[dict[str, str]]:
    if "企业级AI落地" in column or "应用系统" in column:
        patterns = [
            ("为什么很多团队明明做出了 demo，最后还是落不到稳定使用？", "落地缺口", "转化题", "主推"),
            ("从模型部署到业务接入，中间最容易被低估的工程层是什么？", "工程中间层", "信任题", "主推"),
            ("如果项目已经能跑，下一步最该补的是评估、权限还是回写？", "下一步排序", "备用题", "备用"),
        ]
        prefix = "[企业AI落地]"
    elif "技术前沿每日速读" in column:
        patterns = [
            ("为什么大家都在跟的热点，真正能落地的往往只剩下流程闭环？", "热点落地", "引流题", "主推"),
            ("这类方向现在最值得先看什么信号，再决定要不要跟进？", "信号判断", "引流题", "主推"),
            ("表面上都在谈智能体，真正值得普通团队先做的其实是哪一步？", "热点取舍", "信任题", "备用"),
        ]
        prefix = "[AI]"
    else:
        patterns = [
            ("为什么这个方向适合承担今天的第二篇，而不是继续压主专栏？", "第二位补位", "引流题", "主推"),
            ("要激活这个专栏，第一批内容最该补方法题、案例题还是判断题？", "激活策略", "信任题", "备用"),
        ]
        prefix = f"[{column}]"

    candidates = []
    for focus in focuses:
        for question, angle, role, priority in patterns:
            title = f"{prefix} {focus} 里，{question}"
            key = _title_key(title)
            if key in history_keys:
                continue
            candidates.append({"title": title, "role": role.replace("备用题", "引流题"), "priority": priority, "angle": angle, "source": "dynamic"})
            history_keys.add(key)
    return candidates


def _latest_library_path(*, base_dir: Path | None, account: str, column: str) -> Path | None:
    if base_dir is None:
        return None
    library_dir = base_dir / "data" / "business" / "topic_libraries"
    if not library_dir.exists():
        return None
    pattern = f"*_{_slugify(account)}_{_slugify(column)}.json"
    matches = sorted(library_dir.glob(pattern), reverse=True)
    return matches[0] if matches else None


def _load_library_candidates(*, base_dir: Path | None, account: str, column: str) -> tuple[list[dict[str, str]], Path | None]:
    path = _latest_library_path(base_dir=base_dir, account=account, column=column)
    if path is None:
        return [], None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], path
    candidates: list[dict[str, str]] = []
    for module in payload.get("modules", []):
        if not isinstance(module, dict):
            continue
        module_name = str(module.get("name") or module.get("module") or "baseline")
        role = str(module.get("role") or "信任题")
        for item in module.get("candidate_topics", []):
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "unused") != "unused":
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            candidates.append(
                {
                    "candidate_id": str(item.get("candidate_id") or "").strip() or None,
                    "title": title,
                    "role": str(item.get("role") or role),
                    "priority": "主推",
                    "angle": module_name,
                    "source": "baseline_library",
                    "module": module_name,
                }
            )
    return candidates, path


def plan_topic_batch_from_live(*, date: str, account: str, snapshot_path: Path, base_dir: Path | None) -> dict[str, Path]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    recent_titles = _recent_titles(snapshot)
    if not recent_titles:
        raise ValueError("live snapshot does not contain article_titles; formal topic planning requires real account facts")

    full_capture = _load_full_capture(snapshot_path)
    historical_titles = _collect_historical_titles(
        snapshot=snapshot,
        full_capture=full_capture,
        base_dir=base_dir,
        account=account,
    )
    history_keys = {_title_key(title) for title in historical_titles}
    signal_corpus = _collect_signal_corpus(
        snapshot=snapshot,
        full_capture=full_capture,
        base_dir=base_dir,
        account=account,
    )

    cluster, scores = _detect_cluster(recent_titles)
    focuses = _select_focuses(cluster, signal_corpus)
    primary_column = _pick_column(snapshot, cluster)
    secondary_column, secondary_column_scores = _pick_secondary_column_with_score(
        snapshot,
        snapshot_path,
        primary_column,
        base_dir=base_dir,
        account=account,
    )
    primary_candidates = _generate_cluster_candidates(cluster, focuses, history_keys, account)
    secondary_candidates = _generate_secondary_candidates(secondary_column, focuses, history_keys) if secondary_column else []
    primary_library_candidates, primary_library_path = _load_library_candidates(
        base_dir=base_dir,
        account=account,
        column=primary_column,
    )
    secondary_library_candidates, secondary_library_path = _load_library_candidates(
        base_dir=base_dir,
        account=account,
        column=secondary_column,
    ) if secondary_column else ([], None)
    if primary_library_candidates:
        primary_candidates = primary_library_candidates + primary_candidates
    if secondary_library_candidates:
        secondary_candidates = secondary_library_candidates + secondary_candidates
    recent_title_set = {_title_key(title) for title in recent_titles}

    topics: list[dict[str, object]] = []

    def _append_candidate(candidate: dict[str, str], topic_column: str, *, split_reason: str) -> None:
        title = candidate["title"]
        title_key = _title_key(title)
        if title_key in recent_title_set:
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
                "candidate_id": candidate.get("candidate_id"),
                "topic_source": candidate.get("source", "dynamic"),
                "topic_module": candidate.get("module"),
                "reason": (
                    f"优先从专栏基线题库中选题，结合实时标题、历史已发文章、反馈/策略信号校验后输出。{split_reason}"
                    if candidate.get("source") == "baseline_library"
                    else f"基于实时标题、历史已发文章、反馈/策略信号重新生成，不再直接复用旧题库。{split_reason}"
                ),
                "expected_value": f"围绕 {candidate['angle']} 补当前内容缺口，同时避免和已发标题直接重复。",
                "why_now": f"当前主线聚类为 {cluster}，并结合市场/反馈语料提取出这些高频焦点：{'、'.join(focuses[:3])}。",
                "cta": "如果你认可这个方向，我可以继续把它扩成当天发文包和正文初稿。",
                "role": "转化题" if candidate["role"] == "转化题" else ("信任题" if candidate["role"] == "信任题" else "引流题"),
                "risk": "若账号实时页面样本仍偏少，建议补抓一次完整专栏历史页再提高置信度。",
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
            split_reason="按照该账号日更两篇尽量分属不同专栏的经营原则，把第二篇放到次级收益/引流位以保持多专栏活性。",
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
        raise ValueError("not enough non-duplicate dynamically generated topic candidates; collect a fuller account snapshot first")

    batch = {
        "account": account,
        "generated_at": str(snapshot.get("captured_at") or f"{date}T10:00:00Z"),
        "batch_strategy": f"Dynamic topic batch generated from live snapshot + historical articles + strategy/feedback signals for {account}; dominant cluster={cluster}.",
        "writing_order": [topic["title"] for topic in topics[:6]],
        "topics": topics,
        "candidate_focuses": focuses,
        "changes_from_previous": [
            "This batch was generated from live facts plus historical article dedupe, not from the old static topic pool.",
            "Historical titles from full-account capture and topic-usage ledger were treated as hard anti-duplication references.",
            "For 技术小甜甜 daily planning, the first two publish slots still prefer different columns when a viable secondary column is visible in live facts.",
        ],
        "source_signals": [
            f"live snapshot: {snapshot_path}",
            f"resolved full capture: {full_capture.get('_resolved_full_capture_path') if isinstance(full_capture, dict) else 'missing'}",
            f"primary baseline library: {primary_library_path if primary_library_path else 'missing'}",
            f"secondary baseline library: {secondary_library_path if secondary_library_path else 'missing'}",
            f"live article count: {len(recent_titles)}",
            f"historical article/title count used for dedupe: {len(historical_titles)}",
            f"detected columns: {', '.join(_column_names(snapshot)[:5]) or 'unknown'}",
            f"dominant cluster: {cluster} -> {scores}",
            f"focuses: {', '.join(focuses)}",
        ],
        "notes": "Formal topic planning should fail closed without same-day live account facts, and should dedupe against latest available historical account capture before proposing topics.",
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
