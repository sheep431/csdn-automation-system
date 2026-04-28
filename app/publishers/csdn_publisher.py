from __future__ import annotations

from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from app.config import CSDN_EDITOR_URL, ELEMENT_TIMEOUT_MS
from app.publishers.base import BasePublisher
from app.schemas.article_task import ArticleTask


class PublisherError(Exception):
    pass


class LoginExpiredError(PublisherError):
    pass


class CaptchaRequiredError(PublisherError):
    pass


class EditorNotReadyError(PublisherError):
    pass


class ResultUncertainError(PublisherError):
    pass


class CSDNPublisher(BasePublisher):
    def __init__(self, page: Page) -> None:
        super().__init__(page)

    async def validate_task(self, task: ArticleTask) -> None:
        if not task.title.strip():
            raise ValueError("title is empty")
        if not task.body_markdown.strip():
            raise ValueError("body_markdown is empty")

    async def open_editor(self) -> None:
        await self.page.goto(CSDN_EDITOR_URL, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

    async def check_login(self) -> bool:
        current_url = self.page.url.lower()

        if "passport" in current_url or "login" in current_url:
            return False

        try:
            body_text = await self.page.locator("body").inner_text(timeout=3000)
        except Exception:
            body_text = ""

        login_markers = [
            "登录",
            "扫码登录",
            "手机号登录",
            "账号登录",
        ]

        editor_markers = [
            "文章标题",
            "保存草稿",
            "发布",
        ]

        if any(marker in body_text for marker in editor_markers):
            return True

        if any(marker in body_text for marker in login_markers):
            return False

        return True

    async def fill_title(self, task: ArticleTask) -> None:
        title_locator_candidates = [
            self.page.get_by_placeholder("请输入文章标题"),
            self.page.locator("input[placeholder*='标题']").first,
            self.page.locator("input").first,
        ]

        locator = await self._pick_first_visible_locator(title_locator_candidates)
        if locator is None:
            raise EditorNotReadyError("could not find title input")

        await locator.click()
        await locator.fill("")
        await locator.fill(task.title)

    async def fill_body(self, task: ArticleTask) -> None:
        await self._wait_editor_ready()

        body_locator = await self._find_body_editor()
        if body_locator is None:
            raise EditorNotReadyError("could not find body editor")

        await body_locator.click()

        try:
            await body_locator.fill(task.body_markdown)
            return
        except Exception:
            pass

        try:
            await self.page.keyboard.press("Control+A")
        except Exception:
            pass

        try:
            await self.page.keyboard.type(task.body_markdown, delay=5)
            return
        except Exception as exc:
            raise EditorNotReadyError(f"body editor input failed: {exc}") from exc

    async def fill_metadata(self, task: ArticleTask) -> None:
        if task.tags:
            try:
                await self._fill_tags(task.tags)
            except Exception:
                pass

    async def save_draft(self, task: ArticleTask) -> dict[str, Any]:
        candidates = [
            self.page.get_by_role("button", name="保存草稿"),
            self.page.get_by_text("保存草稿", exact=False),
            self.page.locator("button:has-text('保存草稿')").first,
        ]

        locator = await self._pick_first_visible_locator(candidates)
        if locator is None:
            raise PublisherError("could not find draft button")

        try:
            if not await locator.is_enabled():
                raise PublisherError("draft button is disabled")
        except Exception:
            pass

        await locator.click()
        await self.page.wait_for_timeout(2500)

        message = await self._read_feedback_text()
        draft_url = self.page.url

        return {
            "message": message,
            "draft_url": draft_url,
        }

    async def publish(self, task: ArticleTask) -> dict[str, Any]:
        candidates = [
            self.page.get_by_role("button", name="发布"),
            self.page.get_by_text("发布", exact=False),
            self.page.locator("button:has-text('发布')").first,
        ]

        locator = await self._pick_first_visible_locator(candidates)
        if locator is None:
            raise PublisherError("could not find publish button")

        await locator.click()
        await self.page.wait_for_timeout(3000)

        return {
            "message": await self._read_feedback_text(),
            "article_url": self.page.url,
        }

    async def verify_result(self, task: ArticleTask) -> dict[str, Any]:
        current_url = self.page.url
        feedback = await self._read_feedback_text()

        return {
            "url": current_url,
            "feedback": feedback,
        }

    async def detect_captcha(self) -> bool:
        keywords = [
            "验证码",
            "滑块",
            "安全验证",
            "请完成验证",
        ]

        try:
            page_text = await self.page.locator("body").inner_text()
        except Exception:
            return False

        return any(keyword in page_text for keyword in keywords)

    async def snapshot_html(self) -> str:
        return await self.page.content()

    async def inspect_editors(self) -> dict[str, int]:
        return {
            "contenteditable": await self.page.locator("[contenteditable='true']").count(),
            "textarea": await self.page.locator("textarea").count(),
            "codemirror": await self.page.locator(".CodeMirror").count(),
            "monaco": await self.page.locator(".monaco-editor").count(),
            "input": await self.page.locator("input").count(),
        }

    async def _wait_editor_ready(self) -> None:
        candidates = [
            self.page.locator("[contenteditable='true']").first,
            self.page.locator(".CodeMirror").first,
            self.page.locator(".monaco-editor").first,
            self.page.locator("textarea").first,
        ]

        locator = await self._pick_first_visible_locator(candidates, timeout_ms=ELEMENT_TIMEOUT_MS)
        if locator is None:
            raise EditorNotReadyError("editor did not become ready")

    async def _find_body_editor(self) -> Locator | None:
        candidates = [
            self.page.locator("[contenteditable='true']").first,
            self.page.locator("textarea").first,
        ]
        return await self._pick_first_visible_locator(candidates)

    async def _fill_tags(self, tags: list[str]) -> None:
        tag_input_candidates = [
            self.page.get_by_placeholder("添加标签"),
            self.page.locator("input[placeholder*='标签']").first,
        ]

        locator = await self._pick_first_visible_locator(tag_input_candidates, timeout_ms=3000)
        if locator is None:
            return

        for tag in tags:
            await locator.click()
            await locator.fill(tag)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(250)

    async def _read_feedback_text(self) -> str | None:
        possible_feedback_nodes = [
            self.page.locator(".toast").first,
            self.page.locator(".message").first,
            self.page.locator("[role='alert']").first,
            self.page.locator(".el-message").first,
        ]

        for node in possible_feedback_nodes:
            try:
                if await node.count() > 0 and await node.is_visible():
                    text = await node.inner_text()
                    text = text.strip()
                    if text:
                        return text
            except PlaywrightError:
                continue

        return None

    async def _pick_first_visible_locator(
        self,
        locators: list[Locator],
        timeout_ms: int = 5000,
    ) -> Locator | None:
        for locator in locators:
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                return locator
            except PlaywrightTimeoutError:
                continue
            except PlaywrightError:
                continue
        return None
