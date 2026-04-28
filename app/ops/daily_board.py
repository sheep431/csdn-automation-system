from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_ACCOUNT_TEMPLATES = (
    {
        "account_profile": "old-traffic",
        "account_label": "老号",
        "goal": "traffic",
        "articles_per_day": 2,
        "strategy": "吸粉/排榜/测试题材",
    },
    {
        "account_profile": "new-main",
        "account_label": "新号",
        "goal": "revenue",
        "articles_per_day": 2,
        "strategy": "重点收益号/稳定垂类/转化导向",
    },
)


def create_daily_board(output_dir: Path, board_date: str | None = None) -> Path:
    day = board_date or date.today().isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)

    slots: list[dict] = []
    for account in _ACCOUNT_TEMPLATES:
        for index in range(1, account["articles_per_day"] + 1):
            slots.append(
                {
                    "slot_id": f"{day}-{account['account_profile']}-{index}",
                    "account_profile": account["account_profile"],
                    "account_label": account["account_label"],
                    "goal": account["goal"],
                    "strategy": account["strategy"],
                    "slot_index": index,
                    "status": "topic_pending",
                    "topic": "",
                    "title": "",
                    "article_source": "manual",
                    "draft_ready": False,
                    "human_review": "pending",
                    "notes": "",
                }
            )

    payload = {
        "date": day,
        "slot_count": len(slots),
        "slots": slots,
    }
    board_path = output_dir / f"{day}.json"
    board_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return board_path
