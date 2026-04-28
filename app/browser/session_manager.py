from __future__ import annotations

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from app.config import (
    BROWSER_CHANNEL,
    HEADLESS,
    PAGE_TIMEOUT_MS,
    get_browser_profile_dir,
)


class BrowserSessionManager:
    def __init__(self, profile_name: str | None = None) -> None:
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self.profile_name = profile_name

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("browser context is not initialized")
        return self._context

    async def launch(self) -> BrowserContext:
        if self._context is not None:
            return self._context

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(get_browser_profile_dir(self.profile_name)),
            headless=HEADLESS,
            channel=BROWSER_CHANNEL,
        )
        self._context.set_default_timeout(PAGE_TIMEOUT_MS)
        self._context.set_default_navigation_timeout(PAGE_TIMEOUT_MS)
        return self._context

    async def new_page(self) -> Page:
        context = await self.launch()

        if context.pages:
            page = context.pages[0]
        else:
            page = await context.new_page()

        page.set_default_timeout(PAGE_TIMEOUT_MS)
        page.set_default_navigation_timeout(PAGE_TIMEOUT_MS)
        return page

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
