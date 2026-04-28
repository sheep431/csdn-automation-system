from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.config import DATA_DIR
from app.schemas.article_task import ArticleTask
from app.schemas.enums import PublishMode

PROCESS_CATEGORIES = ("flows", "reviews")


def resolve_process_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "process"
    return base_dir / "data" / "process"


def ensure_process_directories(base_dir: Path | None) -> Path:
    root = resolve_process_root(base_dir)
    for category in PROCESS_CATEGORIES:
        (root / category).mkdir(parents=True, exist_ok=True)
    (base_dir / "data" / "tasks" / "pending" if base_dir is not None else DATA_DIR / "tasks" / "pending").mkdir(parents=True, exist_ok=True)
    return root


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "untitled"


def _task_dir(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "tasks" / "pending"
    return base_dir / "data" / "tasks" / "pending"


def _write_markdown(
    *,
    category: str,
    date: str,
    title: str,
    body_lines: Iterable[str],
    base_dir: Path | None,
    file_stem: str,
) -> Path:
    root = ensure_process_directories(base_dir)
    output_dir = root / category
    output_path = output_dir / f"{date}_{file_stem}.md"

    lines = [f"# {title}", "", f"- 日期: {date}"]
    lines.extend(body_lines)
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _load_brief_title(source_brief_path: Path | None) -> str | None:
    if source_brief_path is None or not source_brief_path.exists():
        return None
    try:
        for line in source_brief_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        return None
    return None


def create_workflow_manifest(
    *,
    date: str,
    account: str,
    title: str,
    column: str,
    body_markdown: str,
    tags: list[str],
    source_brief_path: Path | None,
    why_now: str | None,
    base_dir: Path | None,
) -> Path:
    source_title = _load_brief_title(source_brief_path)
    body_preview = [line for line in body_markdown.splitlines()[:8] if line.strip()]
    body_lines = [
        f"- 账号: {account}",
        f"- 专栏/栏目: {column}",
        f"- 主题: {title}",
        f"- 标签: {', '.join(tags) if tags else '无'}",
        f"- 状态: waiting_review",
    ]
    if source_brief_path:
        body_lines.append(f"- 来源业务单: {source_brief_path}")
    if source_title:
        body_lines.append(f"- 来源业务单标题: {source_title}")
    if why_now:
        body_lines.append(f"- 为什么现在做: {why_now}")

    body_lines.extend(
        [
            "",
            "## 主流程",
            "1. 从业务层选题决策确认题目与账号归属",
            "2. 生成对应的草稿任务",
            "3. 保存草稿并导出审核包",
            "4. 等待人工审核",
            "5. 审核通过后进入发布，未通过则退回修改",
            "",
            "## 人与系统分工",
            "- 人负责：判断题值不值得写、是否适配账号、是否可以发布",
            "- 系统负责：生成任务、保留流程记录、导出审核信息、记录状态",
            "",
            "## 异常分支",
            "- 业务单缺失：回到业务层补齐选题信息",
            "- 草稿生成失败：保留失败上下文并停止进入审核",
            "- 审核拒绝：记录原因并退回修改",
            "- 发布失败：保留草稿和审核信息，等待重试",
            "",
            "## 草稿预览",
        ]
    )
    if body_preview:
        for line in body_preview:
            body_lines.append(f"- {line}")
    else:
        body_lines.append("- 暂无正文预览")

    file_stem = _slugify(title)
    return _write_markdown(
        category="flows",
        date=date,
        title=f"流程层执行单：{title}",
        body_lines=body_lines,
        base_dir=base_dir,
        file_stem=file_stem,
    )


def materialize_workflow_task(
    *,
    date: str,
    account: str,
    title: str,
    body_markdown: str,
    tags: list[str],
    column: str,
    source_brief_path: Path | None,
    why_now: str | None,
    base_dir: Path | None,
) -> Path:
    ensure_process_directories(base_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    article_id = f"workflow-{timestamp}-{_slugify(title)[:24]}"
    task = ArticleTask(
        task_id=f"task_{timestamp}",
        article_id=article_id,
        title=title,
        body_markdown=body_markdown,
        tags=tags,
        category=column,
        source="process_workflow",
        publish_mode=PublishMode.DRAFT,
        metadata={
            "account_profile": account,
            "process_profile": account,
            "requires_human_review": True,
            "review_status": "pending",
            "workflow_stage": "waiting_review",
            "workflow_date": date,
            "source_brief_path": str(source_brief_path) if source_brief_path else None,
            "why_now": why_now,
        },
    )

    task_dir = _task_dir(base_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / f"{article_id}.json"
    task_path.write_text(json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return task_path


def _append_section(lines: list[str], title: str, files: list[Path], root: Path) -> None:
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


def review_process(*, date: str, base_dir: Path | None, account: str | None = None) -> Path:
    root = ensure_process_directories(base_dir)
    output_dir = root / "reviews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date}-process-review.md"

    grouped: dict[str, list[Path]] = defaultdict(list)
    for category in PROCESS_CATEGORIES:
        category_dir = root / category
        if not category_dir.exists():
            continue
        for file_path in sorted(category_dir.glob("*.md")):
            grouped[category].append(file_path)

    lines = ["# 流程层复盘", "", f"- 日期: {date}"]
    if account:
        lines.append(f"- 账号: {account}")
    lines.append("")

    _append_section(lines, "流程概览", grouped.get("flows", []), root)
    _append_section(lines, "复盘记录", grouped.get("reviews", []), root)

    lines.append("## 异常与补救")
    lines.append("- 如果业务单缺失，回到第 2 层补齐选题决策")
    lines.append("- 如果草稿任务缺失，回到任务生成步骤补建任务")
    lines.append("- 如果审核信息缺失，停止进入发布步骤")
    lines.append("")

    lines.append("## 下一步动作")
    lines.append("- 把通过业务层的选题直接变成待审任务")
    lines.append("- 保留每一步的输入输出和状态")
    lines.append("- 把异常分支和补救动作写进固定流程")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
