from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.config import DATA_DIR
from app.state import build_daily_column_allocations_from_slots


DEFAULT_WRITING_REQUIREMENT = """This GPT specializes in writing CSDN-style articles based on key points provided by the user, targeting a technical audience. When a user provides specific points, the GPT will organize and expand these into a structured and detailed article, enhancing it with relevant examples, descriptions, and a headline. The headline format should include a topic area in brackets, like '[AI] How to Get Started with Machine Learning'.

The article should be clear, professional, and engaging, broken into well-organized sections with subheadings for each key point. The GPT will ensure formatting consistency, making use of headers, lists, code blocks, and other elements where needed. Each article will conclude with a structured recap or summary of key points.

Articles should aim for around 2000 words in length to meet high-quality scoring standards on CSDN, ensuring depth of explanation, rich detail, and reasonable segmentation across sections. Each section should be expanded thoroughly, maintaining logical flow and providing practical insights.

If additional information is needed to better develop the article, the GPT will either expand based on reasonable assumptions or request clarification from the user."""


def _slugify(value: str) -> str:
    cleaned = []
    for ch in value.strip().lower():
        if ch.isalnum() or ch in {"-", "_"} or "\u4e00" <= ch <= "\u9fff":
            cleaned.append(ch)
        else:
            cleaned.append("-")
    result = "".join(cleaned).strip("-_.")
    while "--" in result:
        result = result.replace("--", "-")
    return result or "untitled"


def resolve_daily_publish_root(base_dir: Path | None) -> Path:
    if base_dir is None:
        return DATA_DIR / "daily_publish"
    return base_dir / "data" / "daily_publish"


def _resolve_daily_plan_path(base_dir: Path | None, date: str) -> Path:
    if base_dir is None:
        return DATA_DIR / "daily_plans" / f"{date}.json"
    return base_dir / "data" / "daily_plans" / f"{date}.json"


def _validate_slot(slot: dict[str, object], index: int) -> dict[str, object]:
    required_fields = [
        "slot_id",
        "account_profile",
        "account_name",
        "goal",
        "title",
        "topic",
        "audience",
        "column",
        "angle",
        "value",
        "cta",
        "why_now",
    ]
    missing = [field for field in required_fields if not str(slot.get(field, "")).strip()]
    if missing:
        raise ValueError(f"slot #{index} missing required fields: {', '.join(missing)}")
    return slot


def _build_writing_prompt(slot: dict[str, object]) -> str:
    keywords = slot.get("keywords") or []
    outline = slot.get("outline") or []
    notes = str(slot.get("notes") or "").strip()
    keyword_lines = "\n".join(f"- {item}" for item in keywords) if keywords else "- 无"
    outline_lines = "\n".join(f"- {item}" for item in outline) if outline else "- 自行按主题展开"
    note_line = notes or "无"
    return f"""你现在要为 CSDN 账号写一篇可直接发布的技术博文，请严格执行下面要求。

一、基础写作规范
{DEFAULT_WRITING_REQUIREMENT}

二、本篇文章任务卡
- 账号定位: {slot['account_name']} ({slot['account_profile']})
- 今日目标: {slot['goal']}
- 文章标题: {slot['title']}
- 主题: {slot['topic']}
- 目标读者: {slot['audience']}
- 专栏/系列: {slot['column']}
- 切入角度: {slot['angle']}
- 核心价值: {slot['value']}
- CTA: {slot['cta']}
- 为什么现在写: {slot['why_now']}
- 备注: {note_line}

三、必须覆盖的关键词
{keyword_lines}

四、建议结构
{outline_lines}

五、输出要求
- 输出完整 Markdown 正文
- 保持标题使用 {slot['title']}
- 开头先说明读者会遇到的实际问题，再给出本文解决路径
- 至少提供 1 个具体示例；如适合，可加入代码块、清单、对比表
- 结尾必须包含“结构化总结”小节，并自然放入 CTA
- 不要写成纯概念堆砌，优先实操、案例、避坑、模板
- 不要输出解释说明，直接输出文章正文
"""


def _build_draft_markdown(slot: dict[str, object]) -> str:
    keywords = slot.get("keywords") or []
    outline = slot.get("outline") or []
    keyword_line = "、".join(str(item) for item in keywords) if keywords else "待补充"
    lines = [
        f"# {slot['title']}",
        "",
        "> 账号定位：{}（{}）".format(slot["account_name"], slot["account_profile"]),
        "> 今日目标：{}".format(slot["goal"]),
        "> 专栏/系列：{}".format(slot["column"]),
        "",
        "## 一、问题背景",
        f"- 目标读者：{slot['audience']}",
        f"- 为什么现在写：{slot['why_now']}",
        f"- 本文核心价值：{slot['value']}",
        "",
        "## 二、正文结构",
    ]
    if outline:
        for item in outline:
            lines.append(f"- {item}")
    else:
        lines.append(f"- 围绕“{slot['topic']}”展开具体问题、步骤和案例")
    lines.extend(
        [
            "",
            "## 三、可直接复用的示例/模板",
            "- 在这里补充案例、代码、模板或清单",
            "",
            "## 四、避坑提醒",
            "- 至少写 2-3 个容易踩坑的点，并给出改法",
            "",
            "## 结构化总结",
            "- 关键结论 1",
            "- 关键结论 2",
            "- 关键结论 3",
            f"- CTA：{slot['cta']}",
            "",
            "## 写作提示",
            f"- 关键词：{keyword_line}",
            "- 目标字数：约 2000 字",
            "- 风格：专业、清晰、可执行、偏 CSDN 技术博文",
            "",
        ]
    )
    return "\n".join(lines)


def prepare_publish_day(*, plan: dict[str, object], base_dir: Path | None) -> dict[str, object]:
    date = str(plan.get("date") or "").strip()
    if not date:
        raise ValueError("plan missing date")

    slots = plan.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("plan must contain a non-empty slots list")

    validated_slots = [_validate_slot(slot, index) for index, slot in enumerate(slots, start=1)]

    publish_root = resolve_daily_publish_root(base_dir) / date
    publish_root.mkdir(parents=True, exist_ok=True)

    board_slots = []
    packet_paths: list[Path] = []
    packet_records: list[dict[str, object]] = []

    for slot in validated_slots:
        slug = _slugify(str(slot["title"]))[:48]
        packet_path = publish_root / f"{slot['slot_id']}_{slug}.json"
        prompt_path = publish_root / f"{slot['slot_id']}_{slug}_prompt.md"
        draft_path = publish_root / f"{slot['slot_id']}_{slug}_draft.md"

        writing_prompt = _build_writing_prompt(slot)
        prompt_path.write_text(writing_prompt + "\n", encoding="utf-8")
        draft_path.write_text(_build_draft_markdown(slot) + "\n", encoding="utf-8")

        packet = {
            "date": date,
            "slot_id": slot["slot_id"],
            "account_profile": slot["account_profile"],
            "account_name": slot["account_name"],
            "goal": slot["goal"],
            "title": slot["title"],
            "topic": slot["topic"],
            "audience": slot["audience"],
            "column": slot["column"],
            "angle": slot["angle"],
            "value": slot["value"],
            "cta": slot["cta"],
            "why_now": slot["why_now"],
            "keywords": slot.get("keywords") or [],
            "outline": slot.get("outline") or [],
            "notes": slot.get("notes") or "",
            "writing_prompt": writing_prompt,
            "prompt_path": str(prompt_path),
            "draft_markdown_path": str(draft_path),
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        packet_paths.append(packet_path)
        packet_records.append(packet)

        board_slots.append(
            {
                "slot_id": slot["slot_id"],
                "account_profile": slot["account_profile"],
                "account_label": slot["account_name"],
                "goal": slot["goal"],
                "strategy": slot["column"],
                "slot_index": len(board_slots) + 1,
                "status": "drafting_ready",
                "topic": slot["topic"],
                "title": slot["title"],
                "article_source": "packet",
                "draft_ready": True,
                "human_review": "pending",
                "notes": slot.get("notes") or "",
            }
        )

    board_payload = {"date": date, "slot_count": len(board_slots), "slots": board_slots}
    board_path = _resolve_daily_plan_path(base_dir, date)
    board_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps(board_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "date": date,
        "board_path": str(board_path),
        "packet_count": len(packet_records),
        "packets": [
            {
                "slot_id": item["slot_id"],
                "account_profile": item["account_profile"],
                "title": item["title"],
                "packet_path": str(path),
                "prompt_path": item["prompt_path"],
                "draft_markdown_path": item["draft_markdown_path"],
            }
            for item, path in zip(packet_records, packet_paths)
        ],
    }
    manifest_json_path = publish_root / f"publish-day_{date}.json"
    manifest_md_path = publish_root / f"publish-day_{date}.md"
    manifest_json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# 当日发文包",
        "",
        f"- 日期: {date}",
        f"- 日排期板: {board_path}",
        f"- 发文包数量: {len(packet_records)}",
        "",
        "## 使用顺序",
        "1. 打开每个 *_prompt.md，把提示词交给写作模型生成正文",
        "2. 把生成结果回填到对应 *_draft.md，人工快速修一遍",
        "3. 用现有 execute-topic / enqueue-markdown / run 流程入队保存草稿",
        "4. 审核通过后再人工发布",
        "",
        "## 当日槽位",
    ]
    for item, path in zip(packet_records, packet_paths):
        md_lines.extend(
            [
                f"### {item['slot_id']} :: {item['title']}",
                f"- 账号: {item['account_name']} ({item['account_profile']})",
                f"- 目标: {item['goal']}",
                f"- 主题: {item['topic']}",
                f"- 包文件: {path}",
                f"- Prompt: {item['prompt_path']}",
                f"- 草稿模板: {item['draft_markdown_path']}",
                "",
            ]
        )
    manifest_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    account_name = str(validated_slots[0].get("account_name") or "").strip()
    allocation_result = build_daily_column_allocations_from_slots(
        date=date,
        account=account_name,
        slots=[
            {
                **slot,
                "slot_index": idx,
            }
            for idx, slot in enumerate(validated_slots, start=1)
        ],
        notes="从 prepare-publish-day 自动生成的当日专栏分配",
        source_signals=[str(manifest_json_path)],
        base_dir=base_dir,
    )

    return {
        "board_path": board_path,
        "manifest_json_path": manifest_json_path,
        "manifest_md_path": manifest_md_path,
        "packet_paths": packet_paths,
        "column_allocation_json_path": allocation_result["json_path"],
        "column_allocation_md_path": allocation_result["md_path"],
        "column_allocation_state_path": allocation_result["state_path"],
    }
