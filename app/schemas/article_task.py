from __future__ import annotations

from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.enums import PublishMode


class ArticleTask(BaseModel):
    task_id: str | None = None
    article_id: str
    title: str
    body_markdown: str
    tags: list[str] = Field(default_factory=list)
    category: str | None = None
    summary: str | None = None
    publish_mode: PublishMode = PublishMode.DRAFT
    source: str = "manual"
    scheduled_at: str | None = None
    priority: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("article_id")
    @classmethod
    def validate_article_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("article_id cannot be empty")
        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be empty")
        if len(value) > 200:
            raise ValueError("title is too long")
        return value

    @field_validator("body_markdown")
    @classmethod
    def validate_body_markdown(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("body_markdown cannot be empty")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []

        for tag in value:
            normalized = tag.strip()
            if not normalized:
                continue
            if normalized not in seen:
                cleaned.append(normalized)
                seen.add(normalized)

        return cleaned

    @model_validator(mode="after")
    def validate_summary(self) -> "ArticleTask":
        if self.summary is not None and len(self.summary.strip()) == 0:
            self.summary = None
        return self

    def normalized_title(self) -> str:
        return self.title.strip()

    def validate_publishable(self, allow_publish: bool) -> None:
        if self.publish_mode == PublishMode.PUBLISH and not allow_publish:
            raise ValueError("publish mode is disabled by configuration")

        if self.publish_mode == PublishMode.PUBLISH and len(self.tags) == 0:
            raise ValueError("publish mode requires at least one tag")

        if self.publish_mode == PublishMode.PUBLISH and not (self.category or "").strip():
            raise ValueError("publish mode requires category")

    def content_hash(self) -> str:
        raw = f"{self.article_id}\n{self.title}\n{self.body_markdown}"
        return sha256(raw.encode("utf-8")).hexdigest()
