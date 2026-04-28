from pathlib import Path
import json

from app.business.ops import process_topic_batch_feedback, is_topic_used
from tests.test_topic_feedback_learning import _sample_batch


def test_batch_level_approval_feedback_auto_marks_remaining_topics_approved(tmp_path: Path):
    batch_path = _sample_batch(tmp_path)

    result = process_topic_batch_feedback(
        date="2026-04-20",
        batch_path=batch_path,
        feedback="这一批可以，照这个来。",
        base_dir=tmp_path,
        account="技术小甜甜",
    )

    payload = json.loads(result["feedback_json_path"].read_text(encoding="utf-8"))
    assert len(payload["usage_sync"]) == 3
    assert all(item["status"] == "approved" for item in payload["usage_sync"])
    assert is_topic_used(title="CSDN 新手起号最小闭环", base_dir=tmp_path, account="技术小甜甜") is True
    assert is_topic_used(title="CSDN 内容战略的底层逻辑", base_dir=tmp_path, account="技术小甜甜") is True
    assert is_topic_used(title="CSDN 发文最容易踩的 5 个坑", base_dir=tmp_path, account="技术小甜甜") is True
