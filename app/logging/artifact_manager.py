from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page

from app.config import SAVE_HTML_SNAPSHOT_ON_ERROR, SCREENSHOT_DIR, SNAPSHOT_DIR
from app.schemas.enums import ExecutionStage


class ArtifactManager:
    def __init__(self) -> None:
        pass

    def build_screenshot_path(self, task_id: str, stage: ExecutionStage | str) -> Path:
        safe_stage = stage.value if hasattr(stage, "value") else str(stage)
        return SCREENSHOT_DIR / f"{task_id}_{safe_stage}.png"

    def build_snapshot_path(self, task_id: str, stage: ExecutionStage | str) -> Path:
        safe_stage = stage.value if hasattr(stage, "value") else str(stage)
        return SNAPSHOT_DIR / f"{task_id}_{safe_stage}.html"

    async def save_screenshot(
        self,
        page: Page,
        task_id: str,
        stage: ExecutionStage | str,
        full_page: bool = True,
    ) -> str | None:
        try:
            path = self.build_screenshot_path(task_id, stage)
            await page.screenshot(path=str(path), full_page=full_page)
            return str(path)
        except Exception:
            return None

    async def save_html_snapshot(
        self,
        page: Page,
        task_id: str,
        stage: ExecutionStage | str,
    ) -> str | None:
        if not SAVE_HTML_SNAPSHOT_ON_ERROR:
            return None

        try:
            path = self.build_snapshot_path(task_id, stage)
            content = await page.content()
            path.write_text(content, encoding="utf-8")
            return str(path)
        except Exception:
            return None
