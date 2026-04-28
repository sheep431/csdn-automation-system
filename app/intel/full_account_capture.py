from __future__ import annotations

import json
import math
import re
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from app.browser.session_manager import BrowserSessionManager
from app.intel.ops import ensure_intel_directories

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
SCRIPT_NUM_RE = re.compile(r"\\b(listTotal|pageSize)\\s*=\\s*(\\d+)\\s*;", re.I)
TITLE_RE = re.compile(r'<h3[^>]*class="[^"]*column_title[^"]*"[^>]*>(.*?)</h3>', re.I | re.S)
DESC_RE = re.compile(r'<span[^>]*class="[^"]*column_text_desc[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
DATA_RE = re.compile(r'<span[^>]*class="[^"]*column_data[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
LI_RE = re.compile(r'<li>(.*?)</li>', re.I | re.S)
H2_TITLE_RE = re.compile(r'<h2[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h2>', re.I | re.S)
ARTICLE_URL_RE = re.compile(r'href="([^"]*/article/details/[^"]+)"', re.I)
ARTICLE_DESC_RE = re.compile(r'<div[^>]*class="[^"]*column_article_desc[^"]*"[^>]*>(.*?)</div>', re.I | re.S)
ARTICLE_TYPE_RE = re.compile(r'<span[^>]*class="[^"]*article-type[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
STATUS_RE = re.compile(r'<span[^>]*class="[^"]*status[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
TAG_RE = re.compile(r'<[^>]+>')


def _capture_paths(*, date: str, account: str, base_dir: Path | None) -> dict[str, Path]:
    root = ensure_intel_directories(base_dir) / "accounts"
    safe = account.replace("/", "-")
    return {
        "json_path": root / f"{date}_{safe}_full.json",
        "md_path": root / f"{date}_{safe}_full.md",
    }


def _normalize_url(url: str) -> str:
    return url.replace("\ufeff", "").strip()


def _make_page_url(canonical_url: str, page: int) -> str:
    base = canonical_url[:-5] if canonical_url.endswith('.html') else canonical_url
    return f"{base}.html" if page <= 1 else f"{base}_{page}.html"


def _parse_script_numbers(html: str) -> tuple[int, int]:
    found = {}
    for key, value in SCRIPT_NUM_RE.findall(html):
        found[key.lower()] = int(value)
    return int(found.get("listtotal", 0)), int(found.get("pagesize", 40)) or 40


def _strip_html(text: str) -> str:
    return unescape(TAG_RE.sub("", text or "")).replace("\xa0", " ").strip()


def _looks_like_verification_page(html: str) -> bool:
    text = _strip_html(html)
    keywords = ["请完成下方验证", "点击按钮进行验证", "安全验证", "图片验证", "滑块验证", "验证后继续访问"]
    return any(keyword in text for keyword in keywords)


def parse_public_column_page(*, html: str, canonical_url: str, page_no: int) -> dict[str, Any]:
    verification_detected = _looks_like_verification_page(html)
    title_match = TITLE_RE.search(html)
    desc_match = DESC_RE.search(html)
    data_match = DATA_RE.search(html)
    title_text = _strip_html(title_match.group(1) if title_match else "")
    desc_text = _strip_html(desc_match.group(1) if desc_match else "")
    data_text = _strip_html(data_match.group(1) if data_match else "")
    count_declared, page_size = _parse_script_numbers(html)
    if count_declared <= 0 and data_text:
        match = re.search(r"文章数[:：]\s*(\d+)", data_text)
        if match:
            count_declared = int(match.group(1))
    articles: list[dict[str, Any]] = []
    for li_html in LI_RE.findall(html):
        title_match = H2_TITLE_RE.search(li_html)
        link_match = ARTICLE_URL_RE.search(li_html)
        if not title_match or not link_match:
            continue
        desc_match = ARTICLE_DESC_RE.search(li_html)
        type_match = ARTICLE_TYPE_RE.search(li_html)
        status_match = STATUS_RE.search(li_html)
        articles.append(
            {
                "page": page_no,
                "title": _strip_html(title_match.group(1)),
                "article_url": link_match.group(1).strip(),
                "summary": _strip_html(desc_match.group(1) if desc_match else ""),
                "article_type": _strip_html(type_match.group(1) if type_match else ""),
                "publish_time": _strip_html(status_match.group(1) if status_match else ""),
            }
        )
    return {
        "column_title": title_text,
        "description": desc_text,
        "article_count_declared": count_declared,
        "page_size": page_size,
        "canonical_url": canonical_url,
        "verification_detected": verification_detected,
        "articles": articles,
    }


def save_full_account_capture(*, date: str, account: str, capture: dict[str, Any], base_dir: Path | None) -> dict[str, Path]:
    paths = _capture_paths(date=date, account=account, base_dir=base_dir)
    payload = {
        "date": date,
        "account": account,
        "captured_at": capture.get("captured_at") or datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "columns": capture.get("columns") or [],
    }
    paths["json_path"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 账号全量专栏与历史内容快照",
        "",
        f"- 日期: {date}",
        f"- 账号: {account}",
        f"- 采集时间: {payload['captured_at']}",
        f"- 专栏数: {len(payload['columns'])}",
        "",
    ]
    for idx, column in enumerate(payload["columns"], start=1):
        lines.extend(
            [
                f"## {idx}. {column.get('title') or '未命名专栏'}",
                f"- 公开链接: {column.get('public_url') or ''}",
                f"- 状态: {column.get('status') or ''}",
                f"- 价格: {column.get('price')}",
                f"- 文章数: {column.get('article_count')}",
                f"- 已抓到文章数: {len(column.get('articles') or [])}",
                f"- 描述: {column.get('description') or ''}",
                "",
            ]
        )
        for article in (column.get("articles") or [])[:12]:
            lines.append(f"- {article.get('title')} :: {article.get('publish_time')}")
        lines.append("")
    paths["md_path"].write_text("\n".join(lines), encoding="utf-8")
    return paths


def _extract_manage_columns(raw_columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    columns: list[dict[str, Any]] = []
    for item in raw_columns:
        title = str(item.get("title") or "").strip()
        public_url = _normalize_url(str(item.get("public_url") or ""))
        if not title or not public_url:
            continue
        columns.append(
            {
                "title": title,
                "description": str(item.get("description") or "").strip(),
                "public_url": public_url,
                "edit_url": str(item.get("edit_url") or "").strip(),
                "manage_url": str(item.get("manage_url") or "").strip(),
                "price": float(item.get("price") or 0),
                "article_count": int(item.get("article_count") or 0),
                "metric_2": int(item.get("metric_2") or 0),
                "status": str(item.get("status") or "").strip(),
                "pay_type": str(item.get("pay_type") or "").strip(),
            }
        )
    return columns


async def _capture_manage_columns(profile: str) -> list[dict[str, Any]]:
    session = BrowserSessionManager(profile_name=profile)
    page = await session.new_page()
    try:
        await page.goto('https://mp.csdn.net/mp_blog/manage/column/allColumnList', wait_until='domcontentloaded')
        await page.wait_for_timeout(5000)
        raw = await page.evaluate(
            r'''() => Array.from(document.querySelectorAll('.column-item')).map(item => {
                const input = item.querySelector('input.edit-box');
                const countLinks = Array.from(item.querySelectorAll('.article-count a')).map(a => (a.innerText || '').trim());
                return {
                  title: input ? (input.value || input.getAttribute('title') || input.dataset.value || '') : '',
                  description: input ? (input.dataset.discript || '') : '',
                  public_url: item.querySelector('a[href*="blog.csdn.net/"][href*="category_"]')?.href || '',
                  edit_url: item.querySelector('a[href*="/columnEdit/"]')?.href || '',
                  manage_url: item.querySelector('a[href*="/columnManage/"]')?.href || '',
                  pay_type: (item.querySelector('.pay-tip')?.innerText || '').trim(),
                  article_count: parseInt(countLinks[0] || '0', 10) || 0,
                  metric_2: parseInt(countLinks[1] || '0', 10) || 0,
                  price: parseFloat(countLinks[2] || '0') || 0,
                  status: (item.querySelector('.column-status')?.innerText || '').trim()
                };
            })'''
        )
        return _extract_manage_columns(raw)
    finally:
        await session.close()


async def _fetch_full_column_with_page(page: Any, public_url: str, article_count: int) -> dict[str, Any]:
    async def load(url: str) -> str:
        await page.goto(url, wait_until='domcontentloaded')
        await page.wait_for_timeout(3500)
        return await page.content()

    first_html = await load(_make_page_url(public_url, 1))
    first = parse_public_column_page(html=first_html, canonical_url=public_url, page_no=1)
    total_pages = max(1, math.ceil((first["article_count_declared"] or article_count or len(first["articles"])) / max(first["page_size"], 1)))
    articles = list(first["articles"])
    seen = {item["title"] for item in articles}
    verification_detected = bool(first.get("verification_detected"))
    for page_no in range(2, total_pages + 1):
        try:
            html = await load(_make_page_url(public_url, page_no))
        except Exception:
            break
        parsed = parse_public_column_page(html=html, canonical_url=public_url, page_no=page_no)
        if parsed.get("verification_detected"):
            verification_detected = True
            await page.wait_for_timeout(6000)
            break
        if not parsed["articles"]:
            break
        for article in parsed["articles"]:
            if article["title"] in seen:
                continue
            seen.add(article["title"])
            articles.append(article)
        await page.wait_for_timeout(1800)
    first["articles"] = articles
    first["total_pages"] = total_pages
    first["verification_detected"] = verification_detected
    return first


async def capture_full_account_content(*, date: str, account: str, profile: str, base_dir: Path | None) -> dict[str, Path]:
    columns = await _capture_manage_columns(profile)
    session = BrowserSessionManager(profile_name=profile)
    page = await session.new_page()
    try:
        full_columns: list[dict[str, Any]] = []
        for column in columns:
            public_url = column["public_url"]
            parsed = await _fetch_full_column_with_page(page, public_url, column["article_count"])
            full_columns.append(
                {
                    **column,
                    "description": parsed.get("description") or column.get("description") or "",
                    "article_count_declared": parsed.get("article_count_declared", 0),
                    "total_pages": parsed.get("total_pages", 1),
                    "articles": parsed.get("articles", []),
                }
            )
    finally:
        await session.close()

    return save_full_account_capture(
        date=date,
        account=account,
        capture={
            "captured_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "columns": full_columns,
        },
        base_dir=base_dir,
    )
