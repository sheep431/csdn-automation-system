from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from app.config import DATA_DIR

RULE_CATEGORIES = ("assessments", "checks", "reviews")


def resolve_rules_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "rules"
    return base_dir / "data" / "rules"


def ensure_rules_directories(base_dir: Path | None) -> Path:
    root = resolve_rules_root(base_dir)
    for category in RULE_CATEGORIES:
        (root / category).mkdir(parents=True, exist_ok=True)
    return root


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "untitled"


def _write_rule_record(
    *,
    category: str,
    date: str,
    title: str,
    body_lines: Iterable[str],
    base_dir: Path | None,
    file_stem: str,
) -> Path:
    root = ensure_rules_directories(base_dir)
    output_dir = root / category
    output_path = output_dir / f"{date}_{file_stem}.md"

    lines = [f"# {title}", "", f"- 日期: {date}"]
    lines.extend(body_lines)
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def score_topic(
    *,
    value_score: int,
    relevance_score: int,
    cost_score: int,
) -> dict[str, object]:
    total = value_score + relevance_score + cost_score
    if value_score >= 4 and relevance_score >= 4 and cost_score >= 4:
        bucket = "A"
    elif value_score >= 3 and relevance_score >= 3:
        bucket = "B"
    else:
        bucket = "C"

    return {
        "value_score": value_score,
        "relevance_score": relevance_score,
        "cost_score": cost_score,
        "total": total,
        "bucket": bucket,
        "recommended": bucket == "A",
    }


def check_draft_readiness(*, title: str, body_markdown: str) -> dict[str, object]:
    reasons: list[str] = []
    cleaned_title = title.strip()
    cleaned_body = body_markdown.strip()
    placeholders = ("TODO", "待补充", "占位", "XXX", "TBD")

    if not cleaned_title or len(cleaned_title) > 200:
        reasons.append("标题清楚")
    if not cleaned_body:
        reasons.append("主题明确")
        reasons.append("结构完整")
    else:
        if len(cleaned_body.splitlines()) < 2:
            reasons.append("结构完整")
        if any(token in cleaned_body for token in placeholders):
            reasons.append("没有大量占位符")

    return {
        "ready": len(reasons) == 0,
        "reasons": reasons,
    }


def check_publish_readiness(*, draft_exists: bool, review_status: str, draft_url: str | None, owner: str | None) -> dict[str, object]:
    reasons: list[str] = []
    if not draft_exists:
        reasons.append("草稿存在")
    if str(review_status).strip().lower() != "approved":
        reasons.append("审核已通过")
    if not draft_url or not draft_url.startswith(("http://", "https://")):
        reasons.append("链接可打开")
    if not owner or not owner.strip():
        reasons.append("发布动作有明确负责人")

    return {
        "publishable": len(reasons) == 0,
        "reasons": reasons,
    }


def review_rules(*, date: str, base_dir: Path | None, account: str | None = None) -> Path:
    root = ensure_rules_directories(base_dir)
    output_dir = root / "reviews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date}-rules-review.md"

    grouped: dict[str, list[Path]] = defaultdict(list)
    for category in ("assessments", "checks"):
        category_dir = root / category
        if not category_dir.exists():
            continue
        for file_path in sorted(category_dir.glob("*.md")):
            grouped[category].append(file_path)

    lines = ["# 规则层复盘", "", f"- 日期: {date}"]
    if account:
        lines.append(f"- 账号: {account}")
    lines.append("")

    lines.append("## 选题分池规则")
    if grouped.get("assessments"):
        lines.append(f"- 记录数: {len(grouped['assessments'])}")
    else:
        lines.append("- 暂无记录")
    lines.append("")

    lines.append("## 草稿合格标准")
    lines.append("- 标题清楚")
    lines.append("- 主题明确")
    lines.append("- 结构完整")
    lines.append("- 没有大量占位符")
    lines.append("")

    lines.append("## 审核通过/退回标准")
    lines.append("- 审核已通过才可进入发布")
    lines.append("- 不符合账号定位或内容过空则退回")
    lines.append("")

    lines.append("## 发布前置条件")
    lines.append("- 草稿存在")
    lines.append("- 审核已通过")
    lines.append("- 链接可打开")
    lines.append("- 发布动作有明确负责人")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def write_rule_score_record(
    *,
    date: str,
    title: str,
    account: str | None,
    value_score: int,
    relevance_score: int,
    cost_score: int,
    base_dir: Path | None,
) -> Path:
    evaluation = score_topic(
        value_score=value_score,
        relevance_score=relevance_score,
        cost_score=cost_score,
    )
    body_lines = [
        f"- 账号: {account or '未指定'}",
        f"- 标题: {title}",
        f"- 价值分: {value_score}",
        f"- 相关分: {relevance_score}",
        f"- 成本分: {cost_score}",
        f"- 总分: {evaluation['total']}",
        f"- 分池: {evaluation['bucket']} 池",
        f"- 推荐: {'是' if evaluation['recommended'] else '否'}",
    ]
    return _write_rule_record(
        category="assessments",
        date=date,
        title=f"规则层选题评分：{title}",
        body_lines=body_lines,
        base_dir=base_dir,
        file_stem=_slugify(title),
    )
