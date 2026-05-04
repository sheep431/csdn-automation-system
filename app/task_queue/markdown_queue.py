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
_ORDERED_LIST_RE = re.compile(r"^\d+[.)]\s+")
_UNORDERED_LIST_RE = re.compile(r"^[-*+]\s+")
_PACKET_JSON_RE = re.compile(r"^\{\s*\"date\"", re.DOTALL)
_ACCOUNT_PROFILE_RE = re.compile(r"^>\s*账号定位[:：]\s*(.*?)（(.*?)）\s*$")
_COLUMN_RE = re.compile(r"^>\s*专栏/系列[:：]\s*(.*?)\s*$")

COLUMN_IMAGE_REGISTRY: dict[str, dict[str, object]] = {
    "技术前沿每日速读": {
        "header_image_alt": "技术前沿每日速读头图",
        "default_tags": ["人工智能", "自动化", "技术趋势"],
    }
}

KEYWORD_TAG_RULES: list[tuple[str, str]] = [
    ("工作流", "工作流"),
    ("智能体", "智能体"),
    ("agent", "智能体"),
    ("dify", "Dify"),
    ("rag", "RAG"),
    ("知识库", "知识库"),
    ("python", "Python"),
    ("godot", "Godot"),
    ("comfyui", "ComfyUI"),
    ("bi", "BI"),
    ("数据可视化", "数据可视化"),
    ("企业ai", "企业AI"),
    ("大模型", "大模型"),
]


def enqueue_markdown_drafts(
    input_path: Path,
    output_dir: Path,
    profile: str,
    source: str = "generated",
    review_status: str = "pending",
    requires_human_review: bool = True,
) -> list[Path]:
    markdown_files = _collect_markdown_files(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for markdown_path in markdown_files:
        task = _build_task_from_markdown(
            markdown_path,
            profile=profile,
            source=source,
            review_status=review_status,
            requires_human_review=requires_human_review,
        )
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


def _build_task_from_markdown(
    path: Path,
    profile: str,
    source: str,
    review_status: str,
    requires_human_review: bool,
) -> ArticleTask:
    raw_body = path.read_text(encoding="utf-8")
    body = _normalize_markdown_for_csdn(raw_body)
    title = _extract_title(body, fallback=path.stem)
    article_id = _build_article_id(path, profile)
    normalized_review_status = review_status.strip().lower() or "pending"
    context = _detect_article_context(path=path, body=body, profile=profile)
    column = context.get("column")
    asset = _resolve_column_assets(column)
    tags = _recommend_tags(title=title, column=column)

    metadata = {
        "account_profile": context.get("account_profile") or profile,
        "review_status": normalized_review_status,
        "requires_human_review": requires_human_review,
        "origin_markdown_path": str(path),
    }
    if context.get("account_name"):
        metadata["account_name"] = context["account_name"]
    if column:
        metadata["column"] = column
    if asset.get("header_image_path"):
        metadata["header_image_path"] = str(asset["header_image_path"])
    if asset.get("header_image_alt"):
        metadata["header_image_alt"] = str(asset["header_image_alt"])
    if asset.get("cover_image_path"):
        metadata["cover_image_path"] = str(asset["cover_image_path"])

    return ArticleTask(
        article_id=article_id,
        title=title,
        body_markdown=body,
        tags=tags,
        category=column,
        publish_mode=PublishMode.DRAFT,
        source=source,
        metadata=metadata,
    )


def _detect_article_context(*, path: Path, body: str, profile: str) -> dict[str, str]:
    sidecar = _load_packet_sidecar(path)
    if sidecar:
        return {
            "account_profile": str(sidecar.get("account_profile") or profile).strip(),
            "account_name": str(sidecar.get("account_name") or "").strip(),
            "column": str(sidecar.get("column") or "").strip(),
        }

    account_name = ""
    account_profile = profile
    column = ""
    for line in body.splitlines()[:12]:
        profile_match = _ACCOUNT_PROFILE_RE.match(line.strip())
        if profile_match:
            account_name = profile_match.group(1).strip()
            account_profile = profile_match.group(2).strip() or profile
            continue
        column_match = _COLUMN_RE.match(line.strip())
        if column_match:
            column = column_match.group(1).strip()
    return {
        "account_profile": account_profile,
        "account_name": account_name,
        "column": column,
    }


def _load_packet_sidecar(path: Path) -> dict[str, object] | None:
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return None
    try:
        raw = sidecar.read_text(encoding="utf-8")
    except OSError:
        return None
    if not _PACKET_JSON_RE.search(raw):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if "column" not in payload and "account_profile" not in payload:
        return None
    return payload


def _resolve_column_assets(column: str | None) -> dict[str, object]:
    if not column:
        return {}
    entry = COLUMN_IMAGE_REGISTRY.get(column)
    if not isinstance(entry, dict):
        return {}
    return entry


def _recommend_tags(*, title: str, column: str | None, max_tags: int = 3) -> list[str]:
    registry_tags = []
    if column:
        registry_tags = [str(item).strip() for item in _resolve_column_assets(column).get("default_tags", []) if str(item).strip()]

    lowered = f"{title} {column or ''}".lower()
    keyword_tags: list[str] = []
    for needle, tag in KEYWORD_TAG_RULES:
        if needle in lowered and tag not in keyword_tags and tag not in registry_tags:
            keyword_tags.append(tag)

    if not registry_tags:
        return keyword_tags[:max_tags]

    result = registry_tags[:max_tags]
    if keyword_tags:
        if len(result) >= max_tags:
            result = result[: max_tags - 1] + [keyword_tags[0]]
        else:
            result.append(keyword_tags[0])
    deduped: list[str] = []
    for tag in result:
        if tag and tag not in deduped:
            deduped.append(tag)
    return deduped[:max_tags]


def _normalize_markdown_for_csdn(body: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    in_code_block = False
    previous_block: str | None = None

    def ensure_blank_line() -> None:
        if output and output[-1] != "":
            output.append("")

    for raw_line in lines:
        stripped = raw_line.strip()

        if stripped.startswith("```"):
            ensure_blank_line()
            output.append(raw_line)
            in_code_block = not in_code_block
            previous_block = "code"
            continue

        if in_code_block:
            output.append(raw_line)
            continue

        if not stripped:
            if output and output[-1] != "":
                output.append("")
            previous_block = None
            continue

        is_heading = stripped.startswith("#")
        is_list = bool(_UNORDERED_LIST_RE.match(stripped) or _ORDERED_LIST_RE.match(stripped))
        is_quote = stripped.startswith(">")

        if is_heading:
            ensure_blank_line()
            output.append(stripped)
            ensure_blank_line()
            previous_block = "heading"
            continue

        if is_list:
            if previous_block not in {"list"}:
                ensure_blank_line()
            output.append(stripped)
            previous_block = "list"
            continue

        if is_quote:
            if previous_block not in {"quote"}:
                ensure_blank_line()
            output.append(stripped)
            previous_block = "quote"
            continue

        if previous_block in {"list", "quote", "code"}:
            ensure_blank_line()
        output.append(stripped)
        previous_block = "paragraph"

    while output and output[-1] == "":
        output.pop()
    return "\n".join(output) + "\n"


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
