from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.browser.session_manager import BrowserSessionManager
from app.business.ops import ensure_business_directories, mark_topic_used
from app.config import CSDN_ARTICLE_LIST_URL
from app.intel.ops import ensure_intel_directories


_CAPTURE_STEPS = (
    ("专栏/专辑列表页", "请打开专栏/专辑管理或列表页，然后点击继续。"),
    ("专栏/专辑数据页", "请打开专栏/专辑数据或收益统计页，然后点击继续。"),
    ("历史题目/文章列表页", "请打开历史文章或专栏内容列表页，然后点击继续。"),
)


def _snapshot_paths(*, date: str, account: str, base_dir: Path | None) -> dict[str, Path]:
    root = ensure_intel_directories(base_dir)
    safe_account = account.replace("/", "-")
    output_dir = root / "accounts"
    return {
        "json_path": output_dir / f"{date}_{safe_account}_live.json",
        "md_path": output_dir / f"{date}_{safe_account}_live.md",
    }


def _business_root(base_dir: Path | None) -> Path:
    return ensure_business_directories(base_dir)


def _ledger_path(base_dir: Path | None) -> Path:
    return _business_root(base_dir) / "topic_usage" / "topic_usage_ledger.json"


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
