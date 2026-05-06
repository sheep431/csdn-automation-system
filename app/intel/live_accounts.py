from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.browser.session_manager import BrowserSessionManager
from app.business.ops import ensure_business_directories, mark_topic_used
from app.config import CSDN_ARTICLE_LIST_URL
from app.intel.ops import ensure_intel_directories
from app.state.ops import get_column_lifecycle


_CAPTURE_STEPS = (
    ("专栏/专辑列表页", "请打开专栏/专辑管理或列表页，然后点击继续。"),
    ("专栏/专辑数据页", "请打开专栏/专辑数据或收益统计页，然后点击继续。"),
    ("历史题目/文章列表页", "请打开历史文章或专栏内容列表页，然后点击继续。"),
)

_COUPON_OVERLAY_TEXT = '请切到“流量券管理”页面；若已看到可用券，保持页面不动，系统将在倒计时后读取并生成使用建议。'
_COUPON_MANAGEMENT_URL_HINTS = ('flowcoupon', 'coupon', 'flow-coupon', '/traffic')
_COUPON_PAGE_TEXT_HINTS = ('流量券管理', '去使用', '每日任务流量券', '曝光')
_COUPON_TARGET_URL_HINTS = ('selectarticle', 'traffic/select', 'promote')
_COUPON_TARGET_TEXT_HINTS = ('选择推广文章', '确认推广', '推广文章', '流量券投放', '我的推广')
_COUPON_CONFIRM_SUCCESS_HINTS = ('推广成功', '使用成功', '投放成功', '推广已创建', '创建成功')
_COUPON_PROMOTION_ACTIVE_HINTS = ('投放中', '推广中', '已推广', '已使用')


def _strip_coupon_overlay_text(text: str) -> str:
    return str(text or '').replace(_COUPON_OVERLAY_TEXT, '').strip()


def _is_coupon_management_page(*, url: str, body_text: str) -> bool:
    normalized_url = str(url or '').strip().lower()
    normalized_text = _strip_coupon_overlay_text(body_text)
    if any(token in normalized_url for token in _COUPON_MANAGEMENT_URL_HINTS):
        return True
    if '流量券管理' not in normalized_text:
        return False
    return sum(1 for token in _COUPON_PAGE_TEXT_HINTS if token in normalized_text) >= 2


def _is_coupon_target_selection_page(*, url: str, body_text: str) -> bool:
    normalized_url = str(url or '').strip().lower()
    normalized_text = _strip_coupon_overlay_text(body_text)
    if any(token in normalized_url for token in _COUPON_TARGET_URL_HINTS):
        return True
    return sum(1 for token in _COUPON_TARGET_TEXT_HINTS if token in normalized_text) >= 2


def _extract_coupon_target_articles(dialog_text: str) -> list[str]:
    titles: list[str] = []
    for raw in str(dialog_text or '').splitlines():
        line = raw.strip()
        if len(line) < 8:
            continue
        if line in {'可推广文章', '确定', '取消', '流量券使用规则'}:
            continue
        if '共 ' in line and '作品' in line:
            continue
        if any(token in line for token in ('审核中文章不可被推广', '流量券可用于本周期内创作文章流量券使用规则')):
            continue
        if line.startswith('[') or '】' in line:
            if line not in titles:
                titles.append(line)
    return titles



def _extract_current_coupon_promotions(body_text: str) -> list[dict[str, str]]:
    promotions: list[dict[str, str]] = []
    in_section = False
    current_title: str | None = None
    for raw in str(body_text or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == '我的推广':
            in_section = True
            current_title = None
            continue
        if not in_section:
            continue
        if line in {'推广明细', '反馈流量券使用感受'}:
            continue
        if line.startswith('[') or '】' in line:
            current_title = line
            continue
        if line in {'推广中', '推广完成', '投放中'} and current_title:
            promotions.append({'title': current_title, 'status': line})
            current_title = None
    return promotions



def _active_coupon_promotions(promotions: list[dict[str, str]]) -> list[dict[str, str]]:
    return [item for item in promotions if str(item.get('status') or '').strip() in {'推广中', '投放中'}]



def _assess_coupon_occupied_state(
    *,
    clicked_use: bool,
    coupon_success_confirmed: bool,
    current_promotions: list[dict[str, str]],
) -> dict[str, Any]:
    active_promotions = _active_coupon_promotions(current_promotions)
    if coupon_success_confirmed:
        return {
            'occupied': True,
            'reason': 'confirmed_in_this_run',
            'active_promotions': active_promotions,
        }
    if active_promotions:
        return {
            'occupied': True,
            'reason': 'existing_active_promotion',
            'active_promotions': active_promotions,
        }
    return {
        'occupied': False,
        'reason': 'no_active_promotion',
        'active_promotions': active_promotions,
    }



def _assess_coupon_slot_state(coupon_entries: list[dict[str, Any]]) -> dict[str, Any]:
    first_coupon = coupon_entries[0] if coupon_entries else None
    if not first_coupon:
        return {
            'has_coupon': False,
            'can_use_now': False,
            'reason': 'no_coupon_found',
            'first_coupon': None,
        }
    action_text = str(first_coupon.get('action_text') or '').strip()
    if action_text == '去使用':
        return {
            'has_coupon': True,
            'can_use_now': True,
            'reason': 'first_coupon_usable',
            'first_coupon': first_coupon,
        }
    if action_text == '已完成':
        return {
            'has_coupon': True,
            'can_use_now': False,
            'reason': 'first_coupon_completed',
            'first_coupon': first_coupon,
        }
    return {
        'has_coupon': True,
        'can_use_now': bool(first_coupon.get('available')),
        'reason': 'first_coupon_unusable',
        'first_coupon': first_coupon,
    }



def _build_coupon_operational_judgment(
    *,
    clicked_use: bool,
    coupon_success_confirmed: bool,
    coupon_occupied: bool,
    active_current_promotions: list[dict[str, str]],
    coupon_slot_state: dict[str, Any],
) -> str:
    if coupon_success_confirmed:
        return '本次已确认挂券成功。'
    if not coupon_slot_state.get('has_coupon'):
        return '当前未见可挂流量券。'
    if coupon_slot_state.get('reason') == 'first_coupon_completed':
        return '当前首张流量券显示已完成，暂无可挂券。'
    if coupon_slot_state.get('can_use_now'):
        return '当前首张流量券可直接去使用，可以挂券。'
    if coupon_occupied or active_current_promotions:
        return '当前有活跃推广，占用中，不建议再挂。'
    if clicked_use:
        return '本次已执行挂券动作，但尚未确认成功，建议人工复核。'
    return '当前存在流量券，但当前不可直接挂券。'



def _build_coupon_strategy_suggestion(recommendation: dict[str, Any] | None) -> str | None:
    if not recommendation:
        return None
    reasons = set(str(item) for item in (recommendation.get('reasons') or []))
    if 'coupon_spread_bonus' in reasons and {'active_revenue', 'flagship_revenue', 'secondary_revenue'} & reasons:
        return '建议策略：收益专栏继续优先挂券，但增加低频专栏的轮转挂券位，避免长期集中。'
    if 'coupon_overused_penalty' in reasons:
        return '建议策略：对近期挂券过密的专栏增加冷却期，避免流量券长期集中在同一列。'
    if {'active_revenue', 'flagship_revenue', '转化题'} <= reasons:
        return '建议策略：继续提高收益型专栏的挂券频次，优先转化题与信任题。'
    return None



def _pick_best_coupon_target_article(*, recommendation_title: str, candidate_titles: list[str]) -> str | None:
    if not candidate_titles:
        return None
    recommendation = _title_key(recommendation_title)
    scored: list[tuple[int, str]] = []
    for title in candidate_titles:
        key = _title_key(title)
        score = 0
        if recommendation and key == recommendation:
            score += 1000
        if recommendation and key and (key in recommendation or recommendation in key):
            score += 200
        overlap = sum(1 for ch in key if ch and ch in recommendation)
        score += overlap
        scored.append((score, title))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]



def _assess_coupon_confirmation(*, url: str, body_text: str, selected_title: str | None) -> dict[str, Any]:
    normalized_text = _strip_coupon_overlay_text(body_text)
    result: dict[str, Any] = {
        'success_confirmed': False,
        'reason': 'no_signal',
        'signals': [],
        'url': url,
    }
    if not normalized_text:
        result['reason'] = 'empty_page'
        return result
    if '可推广文章' in normalized_text or (
        _is_coupon_target_selection_page(url=url, body_text=normalized_text)
        and any(token in normalized_text for token in ('确定', '取消', '共 '))
    ):
        result['reason'] = 'selection_dialog_still_open'
        return result

    success_signals = [token for token in _COUPON_CONFIRM_SUCCESS_HINTS if token in normalized_text]
    if success_signals:
        result['success_confirmed'] = True
        result['reason'] = 'success_signal'
        result['signals'] = success_signals
        return result

    selected_key = _title_key(selected_title or '')
    text_key = _title_key(normalized_text)
    if selected_key and selected_key in text_key and '我的推广' in normalized_text:
        result['success_confirmed'] = True
        result['reason'] = 'my_promotion_listing'
        result['signals'] = [token for token in _COUPON_PROMOTION_ACTIVE_HINTS if token in normalized_text]
        return result

    if selected_key and selected_key in text_key and any(token in normalized_text for token in _COUPON_PROMOTION_ACTIVE_HINTS):
        result['success_confirmed'] = True
        result['reason'] = 'article_visible_with_active_status'
        result['signals'] = [token for token in _COUPON_PROMOTION_ACTIVE_HINTS if token in normalized_text]
        return result
    return result


async def _read_body_text(page: Any) -> str:
    try:
        return _strip_coupon_overlay_text(await page.locator('body').inner_text())
    except Exception:
        return ''


async def _goto_coupon_management_page(page: Any) -> dict[str, Any]:
    attempts: list[str] = []

    async def _capture_state(label: str) -> dict[str, Any]:
        body_text = await _read_body_text(page)
        return {
            'label': label,
            'url': page.url,
            'body_text': body_text,
            'is_coupon_page': _is_coupon_management_page(url=page.url, body_text=body_text),
        }

    current = await _capture_state('initial')
    attempts.append(f"initial:{current['url']}")
    if current['is_coupon_page']:
        return {'ok': True, 'attempts': attempts, 'state': current}

    click_candidates = (
        page.get_by_role('link', name='流量券管理').first,
        page.get_by_role('button', name='流量券管理').first,
        page.locator("a:has-text('流量券管理')").first,
        page.locator("button:has-text('流量券管理')").first,
        page.locator("text=流量券管理").first,
    )
    for idx, candidate in enumerate(click_candidates, start=1):
        try:
            if await candidate.is_visible(timeout=1500):
                await candidate.click(force=True)
                await page.wait_for_timeout(2500)
                current = await _capture_state(f'click_{idx}')
                attempts.append(f"click_{idx}:{current['url']}")
                if current['is_coupon_page']:
                    return {'ok': True, 'attempts': attempts, 'state': current}
        except Exception:
            continue

    direct_urls = (
        'https://mp.csdn.net/mp_blog/manage/traffic?spm=1011.2415.3001.10055',
        'https://mp.csdn.net/mp_blog/manage/flowCoupon',
        'https://mp.csdn.net/mp_blog/manage/flowcoupon',
        'https://mp.csdn.net/mp_blog/manage/coupon',
    )
    for idx, url in enumerate(direct_urls, start=1):
        try:
            await page.goto(url, wait_until='domcontentloaded')
            await page.wait_for_timeout(2500)
            current = await _capture_state(f'goto_{idx}')
            attempts.append(f"goto_{idx}:{current['url']}")
            if current['is_coupon_page']:
                return {'ok': True, 'attempts': attempts, 'state': current}
        except Exception:
            attempts.append(f'goto_{idx}:error')
            continue

    return {'ok': False, 'attempts': attempts, 'state': current}


def _snapshot_paths(*, date: str, account: str, base_dir: Path | None) -> dict[str, Path]:
    root = ensure_intel_directories(base_dir)
    safe_account = account.replace("/", "-")
    output_dir = root / "accounts"
    return {
        "json_path": output_dir / f"{date}_{safe_account}_live.json",
        "md_path": output_dir / f"{date}_{safe_account}_live.md",
    }


def _followup_report_path(*, date: str, account: str, base_dir: Path | None) -> Path:
    root = ensure_intel_directories(base_dir)
    safe_account = account.replace("/", "-")
    return root / "accounts" / f"{date}_{safe_account}_coupon-followup.md"


def _business_root(base_dir: Path | None) -> Path:
    return ensure_business_directories(base_dir)


def _ledger_path(base_dir: Path | None) -> Path:
    return _business_root(base_dir) / "topic_usage" / "topic_usage_ledger.json"



def _coupon_usage_dir(base_dir: Path | None) -> Path:
    path = _business_root(base_dir) / 'coupon_usage'
    path.mkdir(parents=True, exist_ok=True)
    return path



def _coupon_usage_ledger_path(base_dir: Path | None) -> Path:
    return _coupon_usage_dir(base_dir) / 'coupon_usage_ledger.json'



def _load_coupon_usage_entries(*, account: str, base_dir: Path | None) -> list[dict[str, Any]]:
    path = _coupon_usage_ledger_path(base_dir)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return []
    entries = payload.get('entries') if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    results: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get('account') or '') != account:
            continue
        results.append(entry)
    return results



def _coupon_usage_context(*, account: str, columns: set[str], base_dir: Path | None) -> dict[str, Any]:
    counts = {column: 0 for column in columns}
    recent: list[str] = []
    entries = _load_coupon_usage_entries(account=account, base_dir=base_dir)
    def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
        return (
            str(item.get('date') or ''),
            str(item.get('used_at') or item.get('updated_at') or item.get('created_at') or ''),
        )
    for entry in sorted(entries, key=_sort_key, reverse=True):
        column = str(entry.get('column') or '').strip()
        if column not in counts:
            continue
        status = str(entry.get('status') or '').strip()
        if status not in {'confirmed', 'success', 'attached'}:
            continue
        counts[column] += 1
        recent.append(column)
    return {'counts': counts, 'recent_columns': recent[:6]}



def _coupon_spread_adjustment(*, column: str, counts: dict[str, int], recent_columns: list[str]) -> tuple[float, list[str]]:
    if not counts:
        return 0.0, []
    min_count = min(counts.values())
    max_count = max(counts.values())
    count = counts.get(column, 0)
    score = 0.0
    reasons: list[str] = []
    if max_count - min_count >= 2 and count == min_count:
        score += 2.5
        reasons.append('coupon_spread_bonus')
    elif max_count - min_count >= 1 and count == min_count:
        score += 1.5
        reasons.append('coupon_spread_bonus')
    if max_count - min_count >= 2 and count == max_count:
        score -= 1.5
        reasons.append('coupon_overused_penalty')
    if recent_columns[:4].count(column) >= 2:
        score -= 1.0
        reasons.append('recent_coupon_cooldown')
    elif recent_columns and recent_columns[0] == column:
        score -= 0.5
        reasons.append('last_coupon_same_column')
    return score, reasons



def _record_coupon_usage(
    *,
    date: str,
    account: str,
    column: str,
    title: str,
    candidate_id: str | None,
    base_dir: Path | None,
    status: str = 'confirmed',
) -> Path:
    path = _coupon_usage_ledger_path(base_dir)
    entries = _load_coupon_usage_entries(account=account, base_dir=base_dir)
    all_entries: list[dict[str, Any]] = []
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(payload, dict) and isinstance(payload.get('entries'), list):
                all_entries = [item for item in payload['entries'] if isinstance(item, dict)]
        except json.JSONDecodeError:
            all_entries = []
    now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    all_entries.append({
        'date': date,
        'account': account,
        'column': column,
        'title': title,
        'candidate_id': candidate_id,
        'status': status,
        'used_at': now,
    })
    path.write_text(json.dumps({'entries': all_entries, 'updated_at': now}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def _title_key(title: str) -> str:
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


def _table_headers(table: dict[str, Any]) -> list[str]:
    return [str(item or "").strip().lower() for item in table.get("headers") or []]


def _extract_article_titles(snapshot: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for page in snapshot.get("pages") or []:
        if not isinstance(page, dict):
            continue

        direct_titles = page.get("article_titles")
        if isinstance(direct_titles, list):
            for item in direct_titles:
                value = str(item or "").strip()
                if len(value) < 6 or value in seen:
                    continue
                seen.add(value)
                titles.append(value)

        for table in page.get("tables") or []:
            if not isinstance(table, dict):
                continue
            headers = _table_headers(table)
            title_indexes = [
                idx
                for idx, header in enumerate(headers)
                if any(token in header for token in ("标题", "title", "article_title", "文章"))
            ]
            if not title_indexes:
                title_indexes = [0]
            for row in table.get("rows") or []:
                if not isinstance(row, list):
                    continue
                for idx in title_indexes:
                    if idx >= len(row):
                        continue
                    value = str(row[idx] or "").strip()
                    if len(value) < 6:
                        continue
                    if value in seen:
                        continue
                    seen.add(value)
                    titles.append(value)
                    break
    return titles


def _extract_column_names(snapshot: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for page in snapshot.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for heading in page.get("headings") or []:
            text = str(heading or "").strip()
            if not text or len(text) < 2:
                continue
            if text in seen:
                continue
            if any(token in text for token in ("专栏", "每日速读", "实战", "档案", "工坊")):
                seen.add(text)
                names.append(text)
    return names


def save_live_account_snapshot(*, date: str, account: str, snapshot: dict[str, Any], base_dir: Path | None) -> dict[str, Path]:
    paths = _snapshot_paths(date=date, account=account, base_dir=base_dir)
    payload = {
        "date": date,
        "account": account,
        "captured_at": snapshot.get("captured_at") or datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "pages": snapshot.get("pages") or [],
        "column_names": _extract_column_names(snapshot),
        "article_titles": _extract_article_titles(snapshot),
    }
    paths["json_path"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 账号实时采集快照",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 采集时间: {payload['captured_at']}",
        f"- 页面数: {len(payload['pages'])}",
        f"- 识别到的专栏/栏目数: {len(payload['column_names'])}",
        f"- 识别到的文章标题数: {len(payload['article_titles'])}",
        "",
        "## 识别到的专栏/栏目",
    ]
    if payload["column_names"]:
        for name in payload["column_names"]:
            lines.append(f"- {name}")
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 识别到的文章标题"])
    if payload["article_titles"]:
        for title in payload["article_titles"][:50]:
            lines.append(f"- {title}")
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 采集页面"])
    for page in payload["pages"]:
        if not isinstance(page, dict):
            continue
        lines.append(f"### {page.get('label') or '未命名页面'}")
        lines.append(f"- URL: {page.get('url') or ''}")
        lines.append(f"- 标题: {page.get('title') or ''}")
        headings = page.get("headings") or []
        if headings:
            lines.append(f"- Heading示例: {', '.join(str(item) for item in headings[:5])}")
        table_count = len(page.get("tables") or [])
        lines.append(f"- 表格数: {table_count}")
        lines.append("")
    paths["md_path"].write_text("\n".join(lines), encoding="utf-8")
    return paths


def _load_ledger(base_dir: Path | None) -> dict[str, Any]:
    path = _ledger_path(base_dir)
    if not path.exists():
        return {"entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _find_topic_in_batches(*, title: str, account: str, base_dir: Path | None) -> tuple[Path, int] | None:
    batch_dir = _business_root(base_dir) / "topic_batches"
    if not batch_dir.exists():
        return None
    title_key = _title_key(title)
    for batch_path in sorted(batch_dir.glob("*.json"), reverse=True):
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        for topic in batch.get("topics") or []:
            if not isinstance(topic, dict):
                continue
            if str(topic.get("account") or batch.get("account") or "") != account:
                continue
            if _title_key(str(topic.get("title") or "")) == title_key:
                return batch_path, int(topic.get("number") or 0)
    return None


def sync_topic_usage_from_live_snapshot(*, date: str, account: str, snapshot_path: Path, base_dir: Path | None) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    live_titles = _extract_article_titles(snapshot)
    ledger = _load_ledger(base_dir)
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]
    matched_titles: list[str] = []
    last_paths: dict[str, Path] = {"ledger_path": _ledger_path(base_dir)}

    for live_title in live_titles:
        title_key = _title_key(live_title)
        existing = next(
            (
                entry for entry in entries
                if entry.get("account") == account and entry.get("title_key") == title_key
            ),
            None,
        )
        if existing and existing.get("status") == "published":
            matched_titles.append(live_title)
            continue
        match = _find_topic_in_batches(title=live_title, account=account, base_dir=base_dir)
        if match is None:
            continue
        batch_path, topic_number = match
        result = mark_topic_used(
            date=date,
            batch_path=batch_path,
            topic_number=topic_number,
            status="published",
            account=account,
            notes=f"来自账号实时采集快照自动同步: {snapshot_path}",
            base_dir=base_dir,
        )
        last_paths.update(result)
        matched_titles.append(live_title)
        ledger = _load_ledger(base_dir)
        entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]

    report_dir = ensure_intel_directories(base_dir) / "accounts"
    report_path = report_dir / f"{date}_{account}_publish-sync.md"
    lines = [
        "# 实时采集发布同步结果",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 快照: {snapshot_path}",
        f"- 检测到的标题数: {len(live_titles)}",
        f"- 同步为已发布的标题数: {len(matched_titles)}",
        "",
        "## 已同步标题",
    ]
    if matched_titles:
        for title in matched_titles:
            lines.append(f"- {title}")
    else:
        lines.append("- 暂无匹配")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result: dict[str, Any] = {
        "snapshot_path": snapshot_path,
        "report_path": report_path,
        "published_count": len(matched_titles),
        "matched_titles": matched_titles,
    }
    result.update(last_paths)
    return result


def detect_flow_coupon_signals(page_texts: list[str]) -> dict[str, Any]:
    positive_patterns = [
        re.compile(r"获得\s*\d+\s*张?流量券"),
        re.compile(r"流量券.{0,12}(到账|可用|已发放|已到账|奖励)"),
        re.compile(r"(赠送|奖励).{0,10}流量券"),
        re.compile(r"流量券.{0,6}\d+\s*张"),
        re.compile(r"\+\s*\d+\s*(曝光|展现|浏览)"),
        re.compile(r"去使用"),
    ]
    matches: list[str] = []
    for text in page_texts:
        normalized = str(text or "").strip()
        if not normalized:
            continue
        for pattern in positive_patterns:
            for hit in pattern.findall(normalized):
                if isinstance(hit, tuple):
                    hit_text = "".join(hit)
                else:
                    hit_text = str(hit)
                matches.append(hit_text or normalized)
            m = pattern.search(normalized)
            if m:
                matches.append(m.group(0))
        if "流量券管理" in normalized and "获得" not in normalized and "奖励" not in normalized and "可用" not in normalized:
            continue
    deduped: list[str] = []
    for item in matches:
        if item and item not in deduped:
            deduped.append(item)
    return {"has_coupon": bool(deduped), "matches": deduped}


def extract_coupon_management_entries(page_texts: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for text in page_texts:
        normalized = str(text or "").strip()
        if not normalized or "流量券" not in normalized:
            continue
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        name = ""
        preferred_coupon_lines = [
            line for line in lines
            if "流量券" in line and line not in {"流量券", "流量券管理", "流量券使用规则"} and "规则" not in line
        ]
        if preferred_coupon_lines:
            name = preferred_coupon_lines[0]
        exposure_match = re.search(r"(\+\s*\d+)\s*(?:\n\s*)?(曝光|展现|浏览)?", normalized)
        exposure = ""
        if exposure_match:
            exposure = exposure_match.group(1)
            if exposure_match.group(2):
                exposure += exposure_match.group(2)
        validity_match = re.search(r"有效期[:：]\s*([^\n]+)", normalized)
        validity = validity_match.group(1).strip() if validity_match else ""
        action_text = ''
        for token in ('去使用', '已完成', '已使用', '去获取'):
            if token in normalized:
                action_text = token
                break
        available = action_text == '去使用' or (not action_text and '可用' in normalized and '无可用' not in normalized)
        if not name and not exposure and not validity and not available:
            continue
        key = (name, exposure, validity)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "name": name or "未命名流量券",
                "exposure": exposure,
                "validity": validity,
                "available": available,
                "action_text": action_text,
                "raw_text": normalized,
            }
        )
    return entries


def _latest_topic_library_paths(*, account: str, base_dir: Path | None) -> list[Path]:
    root = ensure_business_directories(base_dir)
    library_dir = root / "topic_libraries"
    if not library_dir.exists():
        return []
    latest_by_column: dict[str, Path] = {}
    account_slug = _title_key(account)
    for path in sorted(library_dir.glob(f"*_{account_slug}_*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        column = str(payload.get("column") or "").strip()
        if not column or column in latest_by_column:
            continue
        latest_by_column[column] = path
    return list(latest_by_column.values())


def _sales_bonus(*, column: str, base_dir: Path | None) -> tuple[float, list[str]]:
    root = ensure_intel_directories(base_dir)
    sales_dir = root / "sales"
    if not sales_dir.exists():
        return 0.0, []
    bonus = 0.0
    reasons: list[str] = []
    for path in sorted(sales_dir.glob("*.md"), reverse=True)[:5]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if column in text:
            bonus += 1.5
            reasons.append(f"sales match: {path.name}")
    return bonus, reasons



def _score_breakdown_map(reasons: list[str]) -> dict[str, float]:
    weights = {
        'active_revenue': 4.0,
        'active_traffic': 2.0,
        'flagship_revenue': 3.0,
        'secondary_revenue': 2.0,
        'traffic_support': 1.0,
        '转化题': 2.5,
        '信任题': 1.5,
        '引流题': 1.0,
        'coupon_spread_bonus': 0.0,
        'coupon_overused_penalty': 0.0,
        'recent_coupon_cooldown': 0.0,
        'last_coupon_same_column': 0.0,
    }
    breakdown: dict[str, float] = {}
    for reason in reasons:
        if reason.startswith('sales match: '):
            breakdown['sales_bonus'] = breakdown.get('sales_bonus', 0.0) + 1.5
        elif reason in weights:
            breakdown[reason] = breakdown.get(reason, 0.0) + weights[reason]
    return breakdown



def _usage_context_summary(usage_context: dict[str, Any]) -> list[dict[str, Any]]:
    counts = dict(usage_context.get('counts') or {})
    recent_columns = list(usage_context.get('recent_columns') or [])
    summary: list[dict[str, Any]] = []
    for column, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        summary.append({
            'column': column,
            'count': count,
            'is_recent': bool(recent_columns and recent_columns[0] == column),
        })
    return summary


def analyze_post_publish_coupon_and_pick_next(*, date: str, account: str, page_texts: list[str], base_dir: Path | None, published_title: str) -> dict[str, Any]:
    coupon = detect_flow_coupon_signals(page_texts)
    report_path = _followup_report_path(date=date, account=account, base_dir=base_dir)
    recommendation: dict[str, Any] | None = None
    usage_context: dict[str, Any] = {'counts': {}, 'recent_columns': []}

    if coupon["has_coupon"]:
        candidate_rows: list[dict[str, Any]] = []
        for library_path in _latest_topic_library_paths(account=account, base_dir=base_dir):
            payload = json.loads(library_path.read_text(encoding="utf-8"))
            column = str(payload.get("column") or "").strip()
            lifecycle = get_column_lifecycle(account=account, column=column, base_dir=base_dir)
            lifecycle_state = str(lifecycle.get("state") or "") if lifecycle else ""
            lifecycle_role = str((lifecycle.get("attributes") or {}).get("role") or "") if lifecycle else ""
            sales_bonus, sales_reasons = _sales_bonus(column=column, base_dir=base_dir)
            for module in payload.get("modules") or []:
                if not isinstance(module, dict):
                    continue
                for candidate in module.get("candidate_topics") or []:
                    if not isinstance(candidate, dict):
                        continue
                    if str(candidate.get("status") or "") != "unused":
                        continue
                    score = 0.0
                    reasons: list[str] = []
                    if lifecycle_state == "active_revenue":
                        score += 4.0
                        reasons.append("active_revenue")
                    elif lifecycle_state == "active_traffic":
                        score += 2.0
                        reasons.append("active_traffic")
                    if lifecycle_role == "flagship_revenue":
                        score += 3.0
                        reasons.append("flagship_revenue")
                    elif lifecycle_role == "secondary_revenue":
                        score += 2.0
                        reasons.append("secondary_revenue")
                    elif lifecycle_role == "traffic_support":
                        score += 1.0
                        reasons.append("traffic_support")
                    role = str(candidate.get("role") or "")
                    if role == "转化题":
                        score += 2.5
                        reasons.append("转化题")
                    elif role == "信任题":
                        score += 1.5
                        reasons.append("信任题")
                    elif role == "引流题":
                        score += 1.0
                        reasons.append("引流题")
                    score += sales_bonus
                    reasons.extend(sales_reasons)
                    candidate_rows.append({
                        "title": str(candidate.get("title") or ""),
                        "candidate_id": candidate.get("candidate_id"),
                        "column": column,
                        "module": candidate.get("module"),
                        "role": role,
                        "score": score,
                        "reasons": reasons,
                    })
        if candidate_rows:
            usage_context = _coupon_usage_context(
                account=account,
                columns={str(item.get('column') or '') for item in candidate_rows if str(item.get('column') or '').strip()},
                base_dir=base_dir,
            )
            for item in candidate_rows:
                spread_score, spread_reasons = _coupon_spread_adjustment(
                    column=str(item.get('column') or ''),
                    counts=dict(usage_context.get('counts') or {}),
                    recent_columns=list(usage_context.get('recent_columns') or []),
                )
                item['score'] = float(item.get('score') or 0.0) + spread_score
                item['reasons'].extend(spread_reasons)
                item['score_breakdown'] = _score_breakdown_map(item['reasons'])
                if spread_score:
                    item['score_breakdown']['spread_adjustment'] = spread_score
            candidate_rows.sort(key=lambda item: float(item.get('score') or 0.0), reverse=True)
            recommendation = candidate_rows[0]

    lines = [
        "# 发布后流量券与下一篇建议",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 刚发布文章: {published_title}",
        f"- 是否检测到流量券: {'是' if coupon['has_coupon'] else '否'}",
    ]
    for item in coupon["matches"]:
        lines.append(f"- 流量券信号: {item}")
    lines.append("")
    lines.append("## 下一篇建议")
    if recommendation:
        lines.extend([
            f"- 标题: {recommendation['title']}",
            f"- 专栏: {recommendation['column']}",
            f"- candidate_id: {recommendation['candidate_id']}",
            f"- 角色: {recommendation['role']}",
            f"- 分数: {recommendation['score']}",
        ])
        for reason in recommendation["reasons"]:
            lines.append(f"- 原因: {reason}")
        if recommendation.get('score_breakdown'):
            lines.append("- 评分拆解:")
            for key, value in recommendation['score_breakdown'].items():
                lines.append(f"  - {key}: {value}")
    else:
        lines.append("- 暂无（未检测到流量券或没有可用候选）")
    usage_summary = _usage_context_summary(usage_context)
    if usage_summary:
        lines.extend(["", "## 挂券轮转摘要"])
        for item in usage_summary:
            marker = ' (最近一次挂券专栏)' if item['is_recent'] else ''
            lines.append(f"- {item['column']}: {item['count']} 次{marker}")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "coupon": coupon,
        "recommendation": recommendation,
        "report_path": report_path,
        "usage_context": usage_context,
        "usage_summary": usage_summary,
    }


def build_coupon_use_plan(*, date: str, account: str, page_texts: list[str], base_dir: Path | None, published_title: str) -> dict[str, Any]:
    followup = analyze_post_publish_coupon_and_pick_next(
        date=date,
        account=account,
        page_texts=page_texts,
        base_dir=base_dir,
        published_title=published_title,
    )
    coupon_entries = extract_coupon_management_entries(page_texts)
    coupon_slot_state = _assess_coupon_slot_state(coupon_entries)
    usage_candidate: dict[str, Any] | None = None
    recommendation = followup.get("recommendation")
    strategy_suggestion = _build_coupon_strategy_suggestion(recommendation if isinstance(recommendation, dict) else None)
    first_available = coupon_slot_state.get('first_coupon') if coupon_slot_state.get('can_use_now') else None
    if recommendation and first_available:
        usage_candidate = {
            **recommendation,
            "coupon_name": first_available.get("name"),
            "coupon_exposure": first_available.get("exposure"),
            "coupon_validity": first_available.get("validity"),
            "action_text": first_available.get("action_text"),
            "mode": "semi_auto",
        }

    lines = [followup["report_path"].read_text(encoding="utf-8").rstrip(), "", "## 流量券管理页使用计划"]
    if coupon_entries:
        for entry in coupon_entries:
            lines.extend([
                f"- 券名: {entry['name']}",
                f"- 曝光: {entry['exposure'] or '未知'}",
                f"- 有效期: {entry['validity'] or '未知'}",
                f"- 可用: {'是' if entry['available'] else '否'}",
                f"- 动作: {entry['action_text'] or '无'}",
            ])
    else:
        lines.append("- 未从流量券管理页解析到可用券块")
    lines.append("")
    lines.append("## 半自动使用建议")
    if usage_candidate:
        lines.extend([
            f"- 建议挂券文章: {usage_candidate['title']}",
            f"- 专栏: {usage_candidate['column']}",
            f"- candidate_id: {usage_candidate['candidate_id']}",
            f"- 对应流量券: {usage_candidate['coupon_name']}",
            f"- 操作模式: {usage_candidate['mode']}",
            "- 建议动作: 打开流量券管理页后点击“去使用”，再人工确认目标文章是否正确",
        ])
    else:
        lines.append("- 暂无（缺少可用券或缺少推荐文章）")
    if strategy_suggestion:
        lines.extend(["", "## 挂券策略建议", f"- {strategy_suggestion}"])
    followup["report_path"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        **followup,
        "coupon_entries": coupon_entries,
        "coupon_slot_state": coupon_slot_state,
        "usage_candidate": usage_candidate,
        "strategy_suggestion": strategy_suggestion,
    }


async def _show_overlay(page: Any, message: str) -> None:
    await page.evaluate(
        """
        (msg) => {
          const id = 'hermes-csdn-live-overlay';
          let root = document.getElementById(id);
          if (!root) {
            root = document.createElement('div');
            root.id = id;
            root.style.position = 'fixed';
            root.style.right = '16px';
            root.style.bottom = '16px';
            root.style.zIndex = '999999';
            root.style.background = 'rgba(0,0,0,0.82)';
            root.style.color = '#fff';
            root.style.padding = '12px 14px';
            root.style.borderRadius = '8px';
            root.style.maxWidth = '360px';
            root.style.fontSize = '14px';
            root.style.lineHeight = '1.45';
            root.innerHTML = '<div id="hermes-csdn-live-msg"></div>';
            document.body.appendChild(root);
          }
          const node = document.getElementById('hermes-csdn-live-msg');
          if (node) node.textContent = msg;
        }
        """,
        message,
    )


async def _capture_page(page: Any, label: str) -> dict[str, Any]:
    headings = await page.locator('h1, h2, h3, .title, .header-title').evaluate_all(
        "nodes => nodes.map(n => (n.innerText || '').trim()).filter(Boolean).slice(0, 20)"
    )
    tables = await page.locator('table').evaluate_all(
        """
        nodes => nodes.slice(0, 10).map(t => ({
          headers: Array.from(t.querySelectorAll('thead th, thead td')).map(x => (x.innerText || '').trim()),
          rows: Array.from(t.querySelectorAll('tbody tr')).slice(0, 20).map(tr =>
            Array.from(tr.querySelectorAll('th, td')).map(td => (td.innerText || '').trim())
          )
        }))
        """
    )
    article_titles = await page.locator('.list-item-title, .article-list-item-txt, .article-list-item-mp').evaluate_all(
        """
        nodes => {
          const seen = new Set();
          const results = [];
          for (const node of nodes) {
            const raw = (node.innerText || '').trim();
            const text = raw.split(/\\n+/)[0].trim();
            if (!text || text.length < 6) continue;
            if (seen.has(text)) continue;
            seen.add(text);
            results.push(text);
            if (results.length >= 80) break;
          }
          return results;
        }
        """
    )
    return {
        "label": label,
        "url": page.url,
        "title": await page.title(),
        "headings": headings,
        "tables": tables,
        "article_titles": article_titles,
    }


async def capture_live_account_snapshot(*, date: str, account: str, profile: str, base_dir: Path | None) -> dict[str, Path]:
    session = BrowserSessionManager(profile_name=profile)
    page = await session.new_page()
    try:
        await page.goto(CSDN_ARTICLE_LIST_URL, wait_until='domcontentloaded')
        await _show_overlay(page, '如未登录，请先完成登录；接下来会按提示打开目标页面并等待你切换。')
        await page.wait_for_timeout(3000)
        pages: list[dict[str, Any]] = []
        for label, tip in _CAPTURE_STEPS:
            await _show_overlay(page, tip)
            await page.wait_for_timeout(12000)
            pages.append(await _capture_page(page, label))
        return save_live_account_snapshot(
            date=date,
            account=account,
            snapshot={
                "captured_at": datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                "pages": pages,
            },
            base_dir=base_dir,
        )
    finally:
        await session.close()


async def refresh_publish_facts_from_account(*, date: str, account: str, profile: str, base_dir: Path | None) -> dict[str, Any]:
    session = BrowserSessionManager(profile_name=profile)
    page = await session.new_page()
    try:
        await page.goto(CSDN_ARTICLE_LIST_URL, wait_until='domcontentloaded')
        await page.wait_for_timeout(2500)
        snapshot_paths = save_live_account_snapshot(
            date=date,
            account=account,
            snapshot={
                "captured_at": datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                "pages": [await _capture_page(page, '历史题目/文章列表页')],
            },
            base_dir=base_dir,
        )
    finally:
        await session.close()

    sync_result = sync_topic_usage_from_live_snapshot(
        date=date,
        account=account,
        snapshot_path=snapshot_paths['json_path'],
        base_dir=base_dir,
    )
    sync_result['snapshot_md_path'] = snapshot_paths['md_path']
    return sync_result


async def prepare_coupon_use_from_management_page(
    *,
    date: str,
    account: str,
    profile: str,
    published_title: str,
    base_dir: Path | None,
    auto_click_use: bool = False,
    wait_seconds: int = 12,
) -> dict[str, Any]:
    session = BrowserSessionManager(profile_name=profile)
    page = await session.new_page()
    try:
        await page.goto(CSDN_ARTICLE_LIST_URL, wait_until='domcontentloaded')
        await _show_overlay(page, '正在自动尝试进入“流量券管理”页面，请稍候。')
        navigation = await _goto_coupon_management_page(page)
        if not navigation.get('ok'):
            await _show_overlay(page, '未能自动进入流量券管理页，保留当前页继续读取；请后续检查菜单结构或补充专用路由。')
            await page.wait_for_timeout(max(wait_seconds, 1) * 1000)
        body_text = await _read_body_text(page)
        plan = build_coupon_use_plan(
            date=date,
            account=account,
            page_texts=[body_text] if body_text else [],
            base_dir=base_dir,
            published_title=published_title,
        )
        current_promotions = _extract_current_coupon_promotions(body_text)
        coupon_slot_state = dict(plan.get('coupon_slot_state') or _assess_coupon_slot_state(plan.get('coupon_entries') or []))
        occupancy = _assess_coupon_occupied_state(
            clicked_use=False,
            coupon_success_confirmed=False,
            current_promotions=current_promotions,
        )
        action_result = {
            'navigation_ok': navigation.get('ok', False),
            'navigation_attempts': navigation.get('attempts', []),
            'attempted_auto_click': auto_click_use,
            'clicked_use': False,
            'clicked_use_locator': None,
            'landing_url': page.url,
            'target_selection_detected': False,
            'target_articles': [],
            'selected_target_article': None,
            'confirm_clicked': False,
            'confirmed_target_article': None,
            'coupon_success_confirmed': False,
            'coupon_success_reason': None,
            'coupon_success_signals': [],
            'coupon_usage_record_path': None,
            'coupon_slot_state': coupon_slot_state,
            'current_promotions': current_promotions,
            'active_current_promotions': occupancy['active_promotions'],
            'coupon_occupied': occupancy['occupied'],
            'coupon_occupied_reason': occupancy['reason'],
            'operational_judgment': _build_coupon_operational_judgment(
                clicked_use=False,
                coupon_success_confirmed=False,
                coupon_occupied=occupancy['occupied'],
                active_current_promotions=occupancy['active_promotions'],
                coupon_slot_state=coupon_slot_state,
            ),
        }
        if auto_click_use and plan.get('usage_candidate'):
            locator = None
            locator_name = None
            for label, candidate in (
                ('p.btn', page.locator("p.btn:has-text('去使用')").first),
                ('button-role', page.get_by_role('button', name='去使用').first),
                ('button-text', page.locator("button:has-text('去使用')").first),
                ('text', page.locator("text=去使用").first),
            ):
                try:
                    if await candidate.is_visible(timeout=2000):
                        locator = candidate
                        locator_name = label
                        break
                except Exception:
                    continue
            if locator is not None:
                await locator.click(force=True)
                await page.wait_for_timeout(2500)
                action_result['clicked_use'] = True
                action_result['clicked_use_locator'] = locator_name
                action_result['landing_url'] = page.url
                try:
                    landing_text = await _read_body_text(page)
                    action_result['landing_text'] = landing_text
                    action_result['target_selection_detected'] = _is_coupon_target_selection_page(url=page.url, body_text=landing_text)
                    if action_result['target_selection_detected']:
                        dialogs = await page.locator('[role="dialog"], .el_mcm-dialog, .el_mcm-overlay-dialog').evaluate_all(
                            "nodes => nodes.map(n => (n.innerText || '').trim()).filter(Boolean)"
                        )
                        source_text = '\n'.join(dialogs) if dialogs else landing_text
                        action_result['target_articles'] = _extract_coupon_target_articles(source_text)
                        selected_title = _pick_best_coupon_target_article(
                            recommendation_title=str((plan.get('usage_candidate') or {}).get('title') or ''),
                            candidate_titles=action_result['target_articles'],
                        )
                        action_result['selected_target_article'] = selected_title
                        if selected_title:
                            try:
                                article_locator = page.locator(f"text={selected_title}").first
                                if await article_locator.is_visible(timeout=2000):
                                    await article_locator.click(force=True)
                                    await page.wait_for_timeout(800)
                                    confirm_locator = None
                                    for candidate in (
                                        page.get_by_role('button', name='确定').first,
                                        page.locator("button:has-text('确定')").first,
                                        page.locator("text=确定").first,
                                    ):
                                        try:
                                            if await candidate.is_visible(timeout=1500):
                                                confirm_locator = candidate
                                                break
                                        except Exception:
                                            continue
                                    if confirm_locator is not None:
                                        await confirm_locator.click(force=True)
                                        await page.wait_for_timeout(2500)
                                        action_result['confirmed_target_article'] = selected_title
                                        action_result['confirm_clicked'] = True
                                        action_result['landing_url'] = page.url
                                        post_confirm_text = await _read_body_text(page)
                                        action_result['post_confirm_text'] = post_confirm_text
                                        confirmation = _assess_coupon_confirmation(
                                            url=page.url,
                                            body_text=post_confirm_text,
                                            selected_title=selected_title,
                                        )
                                        action_result['coupon_success_confirmed'] = confirmation['success_confirmed']
                                        action_result['coupon_success_reason'] = confirmation['reason']
                                        action_result['coupon_success_signals'] = confirmation['signals']
                                        action_result['current_promotions'] = _extract_current_coupon_promotions(post_confirm_text)
                                        occupancy = _assess_coupon_occupied_state(
                                            clicked_use=action_result['clicked_use'],
                                            coupon_success_confirmed=action_result['coupon_success_confirmed'],
                                            current_promotions=action_result['current_promotions'],
                                        )
                                        action_result['active_current_promotions'] = occupancy['active_promotions']
                                        action_result['coupon_occupied'] = occupancy['occupied']
                                        action_result['coupon_occupied_reason'] = occupancy['reason']
                                        action_result['operational_judgment'] = _build_coupon_operational_judgment(
                                            clicked_use=action_result['clicked_use'],
                                            coupon_success_confirmed=action_result['coupon_success_confirmed'],
                                            coupon_occupied=action_result['coupon_occupied'],
                                            active_current_promotions=action_result['active_current_promotions'],
                                            coupon_slot_state=action_result['coupon_slot_state'],
                                        )
                                        if action_result['coupon_success_confirmed']:
                                            candidate = plan.get('usage_candidate') or {}
                                            record_path = _record_coupon_usage(
                                                date=date,
                                                account=account,
                                                column=str(candidate.get('column') or ''),
                                                title=str(candidate.get('title') or selected_title or ''),
                                                candidate_id=str(candidate.get('candidate_id') or '') or None,
                                                base_dir=base_dir,
                                            )
                                            action_result['coupon_usage_record_path'] = str(record_path)
                            except Exception:
                                pass
                except Exception:
                    action_result['landing_text'] = ''
        report_path = plan['report_path']
        extra_lines = [
            '',
            '## 半自动执行结果',
            f"- navigation_ok: {'是' if action_result['navigation_ok'] else '否'}",
            f"- navigation_attempts: {' | '.join(action_result['navigation_attempts']) if action_result['navigation_attempts'] else '无'}",
            f"- attempted_auto_click: {'是' if action_result['attempted_auto_click'] else '否'}",
            f"- clicked_use: {'是' if action_result['clicked_use'] else '否'}",
            f"- clicked_use_locator: {action_result['clicked_use_locator'] or '无'}",
            f"- landing_url: {action_result['landing_url']}",
            f"- target_selection_detected: {'是' if action_result['target_selection_detected'] else '否'}",
            f"- selected_target_article: {action_result['selected_target_article'] or '无'}",
            f"- confirm_clicked: {'是' if action_result['confirm_clicked'] else '否'}",
            f"- confirmed_target_article: {action_result['confirmed_target_article'] or '无'}",
            f"- coupon_success_confirmed: {'是' if action_result['coupon_success_confirmed'] else '否'}",
            f"- coupon_success_reason: {action_result['coupon_success_reason'] or '无'}",
            f"- first_coupon_can_use_now: {'是' if action_result['coupon_slot_state'].get('can_use_now') else '否'}",
            f"- first_coupon_reason: {action_result['coupon_slot_state'].get('reason') or '无'}",
            f"- first_coupon_action_text: {((action_result['coupon_slot_state'].get('first_coupon') or {}).get('action_text') or '无')}",
            f"- coupon_occupied: {'是' if action_result['coupon_occupied'] else '否'}",
            f"- coupon_occupied_reason: {action_result['coupon_occupied_reason'] or '无'}",
            f"- operational_judgment: {action_result['operational_judgment']}",
            f"- active_current_promotion_count: {len(action_result['active_current_promotions'])}",
            f"- current_promotion_count: {len(action_result['current_promotions'])}",
        ]
        if action_result.get('target_articles'):
            for title in action_result['target_articles']:
                extra_lines.append(f"- target_article: {title}")
        if action_result.get('coupon_success_signals'):
            for signal in action_result['coupon_success_signals']:
                extra_lines.append(f"- coupon_success_signal: {signal}")
        if action_result.get('active_current_promotions'):
            for promo in action_result['active_current_promotions']:
                extra_lines.append(f"- active_current_promotion: {promo['status']} | {promo['title']}")
        if action_result.get('current_promotions'):
            for promo in action_result['current_promotions']:
                extra_lines.append(f"- current_promotion: {promo['status']} | {promo['title']}")
        if action_result.get('clicked_use') and not action_result.get('coupon_success_confirmed'):
            extra_lines.append('- 下一步: 请人工检查是否出现“推广成功/我的推广/已使用”等信号，以确认挂券是否真正生效。')
        report_path.write_text(report_path.read_text(encoding='utf-8').rstrip() + '\n' + '\n'.join(extra_lines) + '\n', encoding='utf-8')
        return {**plan, 'action_result': action_result}
    finally:
        await session.close()
