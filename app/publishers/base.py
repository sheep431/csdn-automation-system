from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Page

from app.schemas.article_task import ArticleTask


class BasePublisher(ABC):
    def __init__(self, page: Page) -> None:
        self.page = page

    @abstractmethod
    async def validate_task(self, task: ArticleTask) -> None:
        raise NotImplementedError

    @abstractmethod
    async def open_editor(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def check_login(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def fill_title(self, task: ArticleTask) -> None:
        raise NotImplementedError

    @abstractmethod
    async def fill_body(self, task: ArticleTask) -> None:
        raise NotImplementedError

    @abstractmethod
    async def fill_metadata(self, task: ArticleTask) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save_draft(self, task: ArticleTask) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def publish(self, task: ArticleTask) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def verify_result(self, task: ArticleTask) -> dict[str, Any]:
        raise NotImplementedError
