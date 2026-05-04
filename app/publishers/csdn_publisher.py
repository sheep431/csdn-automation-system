from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from app.config import CSDN_EDITOR_URL, ELEMENT_TIMEOUT_MS
from app.publishers.base import BasePublisher
from app.publishers.body_assets import insert_header_image_after_first_blockquote
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

    async def open_editor(self, task: ArticleTask | None = None) -> None:
        editor_url = CSDN_EDITOR_URL
        if task is not None:
            draft_url = str(task.metadata.get("draft_url") or "").strip()
            if draft_url.startswith(("http://", "https://")):
                editor_url = draft_url
        await self.page.goto(editor_url, wait_until="domcontentloaded")
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

        final_markdown = await self._materialize_body_markdown(task)

        await body_locator.click()

        if await self._set_markdown_source(final_markdown):
            return

        try:
            await body_locator.fill(final_markdown)
            return
        except Exception:
            pass

        try:
            await self.page.keyboard.press("Control+A")
        except Exception:
            pass

        try:
            await self.page.keyboard.type(final_markdown, delay=5)
            return
        except Exception as exc:
            raise EditorNotReadyError(f"body editor input failed: {exc}") from exc

    async def fill_metadata(self, task: ArticleTask) -> None:
        await self._ensure_publish_settings_open()
        await self._fill_summary(task)
        await self._fill_tags(task.tags)
        await self._select_column(task.category)
        await self._set_creation_statement_default()
        await self._set_original_and_public()
        await self._upload_cover_image(task)

    async def save_draft(self, task: ArticleTask) -> dict[str, Any]:
        try:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(300)
        except Exception:
            pass

        locator = await self._pick_first_visible_locator(
            [
                self.page.get_by_role("button", name="保存草稿"),
                self.page.locator("button:has-text('保存草稿')").first,
                self.page.get_by_role("button", name="保存为草稿"),
                self.page.locator("button:has-text('保存为草稿')").first,
            ]
        )
        if locator is None:
            raise PublisherError("could not find draft button")

        try:
            if not await locator.is_enabled():
                raise PublisherError("draft button is disabled")
        except Exception:
            pass

        await locator.click(force=True)
        await self.page.wait_for_timeout(2500)

        message = await self._read_feedback_text()
        draft_url = self.page.url

        return {
            "message": message,
            "draft_url": draft_url,
        }

    async def publish(self, task: ArticleTask) -> dict[str, Any]:
        open_locator = await self._pick_first_visible_locator(
            [
                self.page.locator("button.btn.btn-publish").first,
                self.page.get_by_role("button", name="发布文章").first,
                self.page.locator("button:has-text('发布文章')").first,
            ]
        )
        if open_locator is None:
            raise PublisherError("could not find publish button")

        try:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(300)
        except Exception:
            pass

        await open_locator.click(force=True)
        await self.page.wait_for_timeout(1500)

        confirm_locator = await self._pick_first_visible_locator(
            [
                self.page.locator("button.btn-b-red.ml16:has-text('发布文章')").first,
                self.page.locator("button.button.btn-b-red.ml16:has-text('发布文章')").first,
                self.page.get_by_role("button", name="发布文章").last,
            ],
            timeout_ms=3000,
        )
        if confirm_locator is not None:
            await confirm_locator.click(force=True)
            await self.page.wait_for_timeout(3000)
        else:
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
            self.page.locator("pre.editor__inner").first,
            self.page.locator("[contenteditable='true']").first,
            self.page.locator("textarea").first,
        ]
        return await self._pick_first_visible_locator(candidates)

    async def _materialize_body_markdown(self, task: ArticleTask) -> str:
        markdown = task.body_markdown
        header_image_path = str(task.metadata.get("header_image_path") or "").strip()
        if not header_image_path:
            return markdown

        image_file = Path(header_image_path)
        if not image_file.exists():
            raise PublisherError(f"header image not found: {header_image_path}")

        uploaded_url = await self._upload_inline_image(image_file)
        alt = str(task.metadata.get("header_image_alt") or "专栏头图").strip() or "专栏头图"
        task.metadata["uploaded_header_image_url"] = uploaded_url
        return insert_header_image_after_first_blockquote(
            markdown,
            f"![{alt}]({uploaded_url})",
        )

    async def _upload_inline_image(self, image_file: Path) -> str:
        image_button = await self._pick_first_visible_locator(
            [
                self.page.get_by_role("button", name="图片"),
                self.page.locator("button:has-text('图片')").first,
            ]
        )
        if image_button is None:
            raise PublisherError("could not find inline image upload button")

        await image_button.click()
        await self.page.wait_for_timeout(1000)

        file_input = self.page.locator("input[type='file'][accept*='image']").first
        try:
            await file_input.wait_for(state="attached", timeout=3000)
        except Exception as exc:
            raise PublisherError("could not find inline image upload input") from exc

        await file_input.set_input_files(str(image_file))

        image_url = None
        editor = self.page.locator("pre.editor__inner").first
        for _ in range(20):
            await self.page.wait_for_timeout(1000)
            try:
                editor_text = await editor.inner_text()
            except Exception:
                editor_text = ""
            match = re.search(r"!\[[^\]]*\]\((https?://[^)]+)\)", editor_text)
            if match:
                image_url = match.group(1)
                break
            body_text = await self.page.locator("body").inner_text()
            match = re.search(r"(https?://i-blog\.csdnimg\.cn/[^\s)]+)", body_text)
            if match:
                image_url = match.group(1)
                break

        if not image_url:
            raise PublisherError("inline image uploaded but URL could not be detected")
        return image_url

    async def _ensure_publish_settings_open(self) -> None:
        if await self._is_publish_settings_open():
            return

        open_button = await self._pick_first_visible_locator(
            [
                self.page.locator("button.btn-publish").first,
                self.page.get_by_role("button", name="发布文章").first,
                self.page.locator("button:has-text('发布文章')").first,
            ],
            timeout_ms=3000,
        )
        if open_button is None:
            raise PublisherError("could not open publish settings")

        await open_button.click()
        await self.page.wait_for_timeout(1500)
        if not await self._is_publish_settings_open():
            raise PublisherError("publish settings did not open")

    async def _is_publish_settings_open(self) -> bool:
        locators = [
            self.page.get_by_role("button", name="保存为草稿"),
            self.page.locator("textarea[placeholder*='默认提取正文前256个字']").first,
            self.page.locator("input[type='checkbox'][value]").first,
        ]
        locator = await self._pick_first_visible_locator(locators, timeout_ms=1000)
        return locator is not None

    async def _fill_summary(self, task: ArticleTask) -> None:
        summary = (task.summary or "").strip()
        if not summary:
            return
        locator = await self._pick_first_visible_locator(
            [self.page.locator("textarea[placeholder*='默认提取正文前256个字']").first],
            timeout_ms=1500,
        )
        if locator is None:
            return
        await locator.click()
        await locator.fill(summary)

    async def _fill_tags(self, tags: list[str]) -> None:
        if not tags:
            return
        add_tag_button = await self._pick_first_visible_locator(
            [
                self.page.locator("button.tag__btn-tag").first,
                self.page.get_by_role("button", name="添加文章标签").first,
            ],
            timeout_ms=2000,
        )
        if add_tag_button is not None:
            try:
                await add_tag_button.click()
                await self.page.wait_for_timeout(500)
            except Exception:
                pass

        tag_input_candidates = [
            self.page.get_by_placeholder("请输入文字搜索，Enter键入可添加自定义标签"),
            self.page.get_by_placeholder("添加标签"),
            self.page.locator("input[placeholder*='标签']").first,
        ]

        locator = await self._pick_first_visible_locator(tag_input_candidates, timeout_ms=3000)
        if locator is None:
            return

        for tag in tags:
            await locator.click()
            await locator.fill("")
            await locator.fill(tag)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(250)

    async def _select_column(self, category: str | None) -> None:
        column = (category or "").strip()
        if not column:
            return

        checkbox = self.page.locator(f"input[type='checkbox'][value='{column}']").first
        try:
            await checkbox.wait_for(state="attached", timeout=3000)
        except Exception:
            return
        try:
            if not await checkbox.is_checked():
                await checkbox.check(force=True)
                await self.page.wait_for_timeout(300)
        except Exception:
            try:
                await self.page.evaluate(
                    """
                    (column) => {
                      const box = document.querySelector(`input[type='checkbox'][value='${column.replace(/'/g, "\\'")}']`);
                      if (!box) return false;
                      box.checked = true;
                      box.dispatchEvent(new Event('change', { bubbles: true }));
                      return true;
                    }
                    """,
                    column,
                )
            except Exception:
                return

    async def _set_creation_statement_default(self) -> None:
        locator = await self._pick_first_visible_locator(
            [self.page.locator("input[placeholder='无声明']").first],
            timeout_ms=1500,
        )
        if locator is None:
            return
        try:
            await locator.click()
            await locator.fill("无声明")
        except Exception:
            return

    async def _set_original_and_public(self) -> None:
        for value in ["original", "public"]:
            locator = self.page.locator(f"input[type='radio'][value='{value}']").first
            try:
                await locator.wait_for(state="attached", timeout=1000)
                if not await locator.is_checked():
                    await locator.check(force=True)
                    await self.page.wait_for_timeout(150)
            except Exception:
                continue

    async def _upload_cover_image(self, task: ArticleTask) -> None:
        cover_path = str(task.metadata.get("cover_image_path") or task.metadata.get("header_image_path") or "").strip()
        if not cover_path:
            return
        image_file = Path(cover_path)
        if not image_file.exists():
            raise PublisherError(f"cover image not found: {cover_path}")

        upload_button = await self._pick_first_visible_locator(
            [
                self.page.locator(".upload-img-box").first,
                self.page.get_by_text("从本地上传", exact=False),
            ],
            timeout_ms=2000,
        )
        if upload_button is not None:
            try:
                await upload_button.click()
                await self.page.wait_for_timeout(300)
            except Exception:
                pass

        file_input = self.page.locator("input.el-upload__input[type='file']").first
        try:
            await file_input.wait_for(state="attached", timeout=3000)
        except Exception:
            return
        await file_input.set_input_files(str(image_file))
        await self.page.wait_for_timeout(1000)

        confirm_button = await self._pick_first_visible_locator(
            [
                self.page.locator(".vicp-operate-btn").first,
                self.page.get_by_text("确认上传", exact=True),
                self.page.locator("text=确认上传").first,
            ],
            timeout_ms=3000,
        )
        if confirm_button is not None:
            try:
                await confirm_button.click(force=True)
            except Exception:
                pass
            await self.page.wait_for_timeout(1500)

        crop_modal = self.page.locator(".vue-image-crop-upload").first
        try:
            if await crop_modal.count() > 0 and await crop_modal.is_visible():
                close_button = await self._pick_first_visible_locator(
                    [
                        self.page.get_by_role("button", name="关闭"),
                        self.page.locator(".modal__close-button").first,
                    ],
                    timeout_ms=1500,
                )
                if close_button is not None:
                    await close_button.click(force=True)
                    await self.page.wait_for_timeout(800)
        except Exception:
            pass

    async def _set_markdown_source(self, markdown: str) -> bool:
        try:
            return bool(
                await self.page.evaluate(
                    """
                    (text) => {
                      const el = document.querySelector('pre.editor__inner, [contenteditable="true"]');
                      if (!el) return false;
                      el.textContent = text;
                      el.dispatchEvent(new InputEvent('input', {
                        bubbles: true,
                        data: text,
                        inputType: 'insertText',
                      }));
                      el.dispatchEvent(new Event('change', { bubbles: true }));
                      return true;
                    }
                    """,
                    markdown,
                )
            )
        except Exception:
            return False

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
