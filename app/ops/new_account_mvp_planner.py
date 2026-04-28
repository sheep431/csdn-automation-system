from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import DATA_DIR


def _normalize_title(title: str) -> str:
    cleaned = []
    for ch in title.strip().lower():
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            cleaned.append(ch)
        else:
            cleaned.append("-")
    result = "".join(cleaned).strip("-")
    while "--" in result:
        result = result.replace("--", "-")
    return result or "untitled"


def _planner_paths(*, date: str, account: str, base_dir: Path | None) -> dict[str, Path]:
    root = (base_dir / "data" / "daily_publish_inputs") if base_dir is not None else (DATA_DIR / "daily_publish_inputs")
    safe = account.replace("/", "-")
    return {
        "json_path": root / f"{date}_{safe}_daily-mvp.json",
        "md_path": root / f"{date}_{safe}_daily-mvp.md",
    }


def _pick_columns(capture: dict[str, Any]) -> list[dict[str, Any]]:
    columns = [item for item in capture.get("columns", []) if isinstance(item, dict)]
    columns = [c for c in columns if str(c.get("status") or "").strip() == "已上架" and float(c.get("price") or 0) > 0]
    columns.sort(key=lambda c: (-(float(c.get("price") or 0)), -(int(c.get("article_count") or 0))))
    return columns


def _candidate_templates(column_title: str) -> list[str]:
    if "Dify" in column_title:
        return [
            "[Dify实战] 工作流调试总卡在中间节点？一套可复用的排查 checklist",
            "[Dify实战] 知识库版本更新策略：如何避免“内容改了，答案还是旧的”",
            "[Dify实战] 从业务案例到可复用模板：怎样把一次项目沉淀成长期资产",
            "[Dify实战] 多应用协作怎么设计？从单点助手到系统化 AI 工具箱",
        ]
    if "企业级AI落地" in column_title or "应用系统" in column_title:
        return [
            "[企业AI落地] 企业内网统一推理网关怎么搭？从 Ollama 到服务封装的工程实践",
            "[AI架构] 从单点 Demo 到生产系统：企业 AI 应用为什么必须补“监控和回滚”",
            "[企业AI落地] 为什么很多内网 AI 项目卡在“能跑”之后？这 4 个工程缺口最常见",
            "[企业AI落地] RAG 上线后怎么做质量回归？一套企业内部可执行的检查流程",
        ]
    if "ComfyUI" in column_title:
        return [
            "[ComfyUI] 工作流越做越乱怎么办？3 步把节点工程整理成可复用模板",
            "[ComfyUI] 批量生图总翻车？从提示词、采样器到节点复用的稳定性排查",
            "[ComfyUI] 从单次出图到批量交付：你需要补上的 4 个工程化环节",
            "[ComfyUI] 做完基础工作流后下一步学什么？一张进阶路线图讲清楚",
        ]
    if "Python" in column_title:
        return [
            "[Python实战] 批量处理日志与报表：一个脚本替代一堆重复操作",
            "[Python] requests、session、cookie 到底什么关系？一篇讲清接口登录态",
        ]
    return [f"[{column_title}] 基于历史内容延续的下一篇实战题"]


def _choose_title(column: dict[str, Any]) -> str:
    published = {_normalize_title(str(item.get('title') or '')) for item in (column.get('articles') or []) if isinstance(item, dict)}
    for title in _candidate_templates(str(column.get("title") or "")):
        if _normalize_title(title) not in published:
            return title
    return f"[{column.get('title')}] 基于历史内容继续扩展的下一篇实战题"


def plan_new_account_daily_mvp(*, date: str, account: str, capture_path: Path, base_dir: Path | None) -> dict[str, Path]:
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    columns = _pick_columns(capture)
    if len(columns) < 2:
        raise ValueError("need at least two active paid columns to build a two-topic different-column daily MVP plan")

    selected = columns[:2]
    slots = []
    for idx, column in enumerate(selected, start=1):
        slots.append(
            {
                "slot_id": f"{date}-new-main-{idx}",
                "account_profile": "new-main",
                "account_name": account,
                "goal": "revenue",
                "title": _choose_title(column),
                "topic": f"{column.get('title')} 延续选题",
                "audience": f"已经关注 {column.get('title')} 且愿意继续购买/阅读该专栏的读者",
                "column": column.get("title"),
                "angle": "基于该专栏历史存量内容，优先补下一个工程缺口或进阶实操点",
                "value": "当日两篇尽量分专栏，形成两个售卖点同时发力，而不是同一专栏连发两篇",
                "cta": f"如果你认可这个方向，我可以继续把它扩成 {column.get('title')} 的正文初稿。",
                "why_now": f"该专栏当前已上架，历史文章数 {column.get('article_count')}，且本次 daily MVP 明确要求两篇尽量分属不同专栏。",
                "keywords": [str(column.get("title")), "历史延续", "专栏MVP"],
                "outline": [
                    f"先回顾 {column.get('title')} 里已经讲过什么",
                    "指出当前还缺哪一块",
                    "给出这篇补位内容的完整结构",
                    "自然承接到专栏购买/后续文章",
                ],
                "notes": f"来源：full account capture {capture_path}",
            }
        )

    payload = {
        "date": date,
        "account": account,
        "slot_count": len(slots),
        "strategy": "new-account-only MVP: two posts per day, prefer two different columns to activate multiple selling points.",
        "capture_path": str(capture_path),
        "slots": slots,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    paths = _planner_paths(date=date, account=account, base_dir=base_dir)
    paths["json_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["json_path"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_lines = [
        "# 新账号每日两篇 MVP 计划",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 数据来源: {capture_path}",
        f"- 策略: {payload['strategy']}",
        "",
    ]
    for idx, slot in enumerate(slots, start=1):
        md_lines.extend([
            f"## {idx}. {slot['title']}",
            f"- 专栏: {slot['column']}",
            f"- 主题: {slot['topic']}",
            f"- Why now: {slot['why_now']}",
            f"- CTA: {slot['cta']}",
            "",
        ])
    paths["md_path"].write_text("\n".join(md_lines), encoding="utf-8")
    return paths
