from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

INTEL_CATEGORIES = ("accounts", "feedback", "competitors", "market", "sales", "insights")

CATEGORY_TITLES = {
    "accounts": "账号表现快照",
    "feedback": "用户反馈记录",
    "competitors": "对标账号与优秀案例",
    "market": "市场与趋势观察",
    "sales": "专栏与转化记录",
    "insights": "经营结论与决策",
}


def resolve_intel_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        from app.config import DATA_DIR

        return DATA_DIR / "intel"
    return base_dir / "data" / "intel"


def ensure_intel_directories(base_dir: Path | None) -> Path:
    root = resolve_intel_root(base_dir)
    for category in INTEL_CATEGORIES:
        (root / category).mkdir(parents=True, exist_ok=True)
    return root


def write_intel_record(
    *,
    category: str,
    date: str,
    title: str,
    body_lines: Iterable[str],
    base_dir: Path | None,
) -> Path:
    root = ensure_intel_directories(base_dir)
    output_dir = root / category
    output_path = output_dir / f"{date}.md"

    lines = [f"# {title}", "", f"- 日期: {date}"]
    lines.extend(body_lines)
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def collect_intel_record(*, kind: str, date: str, account: str | None, summary: str, base_dir: Path | None) -> Path:
    title = CATEGORY_TITLES.get(kind, kind)
    body_lines = []
    if account:
        body_lines.append(f"- 账号: {account}")
    body_lines.append(f"- 摘要: {summary}")
    return write_intel_record(category=kind, date=date, title=title, body_lines=body_lines, base_dir=base_dir)


def log_feedback_record(
    *,
    date: str,
    account: str | None,
    source: str,
    feedback_type: str,
    content: str,
    base_dir: Path | None,
) -> Path:
    body_lines = [
        f"- 来源: {source}",
        f"- 类型: {feedback_type}",
    ]
    if account:
        body_lines.append(f"- 账号: {account}")
    body_lines.append(f"- 内容: {content}")
    return write_intel_record(
        category="feedback",
        date=date,
        title=CATEGORY_TITLES["feedback"],
        body_lines=body_lines,
        base_dir=base_dir,
    )


def log_competitor_record(
    *,
    date: str,
    account: str | None,
    url: str,
    notes: str,
    tag: str | None,
    base_dir: Path | None,
) -> Path:
    body_lines = [f"- 链接: {url}"]
    if account:
        body_lines.append(f"- 账号: {account}")
    if tag:
        body_lines.append(f"- 标签: {tag}")
    body_lines.append(f"- 观察: {notes}")
    return write_intel_record(
        category="competitors",
        date=date,
        title=CATEGORY_TITLES["competitors"],
        body_lines=body_lines,
        base_dir=base_dir,
    )


def log_sales_record(
    *,
    date: str,
    account: str | None,
    column: str,
    metric: str,
    value: str,
    notes: str | None,
    base_dir: Path | None,
) -> Path:
    body_lines = [
        f"- 专栏: {column}",
        f"- 指标: {metric}",
        f"- 数值: {value}",
    ]
    if account:
        body_lines.append(f"- 账号: {account}")
    if notes:
        body_lines.append(f"- 备注: {notes}")
    return write_intel_record(
        category="sales",
        date=date,
        title=CATEGORY_TITLES["sales"],
        body_lines=body_lines,
        base_dir=base_dir,
    )


def _format_period_label(period: str, date: str) -> tuple[str, str, str]:
    if period == "week":
        return "本周经营输入复盘", "经营判断", "下周动作"
    if period == "month":
        try:
            month_num = int(datetime.strptime(date, "%Y-%m-%d").strftime("%m"))
            month_label = f"{month_num} 月"
        except ValueError:
            month_label = "本月"
        return f"{month_label}经营输入月报", "本月结论", "下月实验计划"
    return f"本{period}经营输入摘要", "经营判断", "后续动作"



def _collect_category_files(root: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for category in ("accounts", "feedback", "competitors", "market", "sales"):
        category_dir = root / category
        if not category_dir.exists():
            continue
        for file_path in sorted(category_dir.glob("*.md")):
            grouped[category].append(file_path)
    return grouped



def _category_files_section_title(category: str) -> str:
    return {
        "accounts": "数据概览",
        "feedback": "用户反馈",
        "competitors": "对标与外部参考",
        "market": "市场与趋势",
        "sales": "专栏与转化信号",
    }[category]



def _append_category_section(lines: list[str], category: str, files: list[Path], root: Path) -> None:
    lines.append(f"## {_category_files_section_title(category)}")
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
        bullets = [line[2:].strip() for line in content if line.startswith("- ")]
        if bullets:
            for bullet in bullets[:3]:
                lines.append(f"  - {bullet}")
    lines.append("")



def review_intel(*, period: str, date: str, base_dir: Path | None, account: str | None = None) -> Path:
    root = ensure_intel_directories(base_dir)
    insight_dir = root / "insights"
    insight_dir.mkdir(parents=True, exist_ok=True)
    output_path = insight_dir / f"{date}-{period}.md"

    grouped = _collect_category_files(root)
    title, judgment_title, next_action_title = _format_period_label(period, date)

    lines = [f"# {title}", "", f"- 日期: {date}"]
    if account:
        lines.append(f"- 账号: {account}")
    lines.append("")

    for category in ("accounts", "feedback", "competitors", "market", "sales"):
        _append_category_section(lines, category, grouped.get(category, []), root)

    lines.append(f"## {judgment_title}")
    lines.append("- 哪些题材值得加重")
    lines.append("- 哪些账号动作应该调整")
    lines.append("- 哪些内容更适合卖专栏")
    lines.append("")

    lines.append(f"## {next_action_title}")
    lines.append("- 继续放大高转化题材")
    lines.append("- 调整低反馈内容的角度或账号归属")
    lines.append("- 测试更直接的引流与 CTA 路径")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
