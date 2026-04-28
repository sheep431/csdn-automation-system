from __future__ import annotations

import json
import re
from pathlib import Path

from app.schemas.article_task import ArticleTask
from app.schemas.enums import PublishMode

_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9._-]+")
_MULTI_DASH_RE = re.compile(r"-+")


def enqueue_markdown_drafts(
    input_path: Path,
    output_dir: Path,
    profile: str,
    source: str = "generated",
) -> list[Path]:
    markdown_files = _collect_markdown_files(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for markdown_path in markdown_files:
        task = _build_task_from_markdown(markdown_path, profile=profile, source=source)
        output_path = output_dir / f"{task.article_id}.json"
        output_path.write_text(
            json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        created.append(output_path)
    return created


def _collect_markdown_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in _MARKDOWN_EXTENSIONS else []

    if input_path.is_dir():
        return sorted(
            path
            for path in input_path.iterdir()
            if path.is_file() and path.suffix.lower() in _MARKDOWN_EXTENSIONS
        )

    raise FileNotFoundError(f"input path does not exist: {input_path}")


def _build_task_from_markdown(path: Path, profile: str, source: str) -> ArticleTask:
    body = path.read_text(encoding="utf-8")
    title = _extract_title(body, fallback=path.stem)
    article_id = _build_article_id(path, profile)
    return ArticleTask(
        article_id=article_id,
        title=title,
        body_markdown=body,
        publish_mode=PublishMode.DRAFT,
        source=source,
        metadata={
            "account_profile": profile,
            "review_status": "pending",
            "requires_human_review": True,
            "origin_markdown_path": str(path),
        },
    )


def _extract_title(body: str, fallback: str) -> str:
    match = _HEADING_RE.search(body)
    if match:
        return match.group(1).strip()
    return fallback.strip() or "untitled"


def _build_article_id(path: Path, profile: str) -> str:
    profile_slug = _slugify(profile)
    stem_slug = _slugify(path.stem)
    return f"{profile_slug}-{stem_slug}".strip("-") or "task"


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    ascii_only = lowered.encode("ascii", errors="ignore").decode("ascii")
    cleaned = _NON_ALNUM_RE.sub("-", ascii_only)
    return _MULTI_DASH_RE.sub("-", cleaned).strip("-") or "draft"
