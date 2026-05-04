from __future__ import annotations

import asyncio

from playwright.async_api import Page

from app.config import ALLOW_PUBLISH, BASE_DIR, RETRY_BACKOFF_SECONDS
from app.browser.session_manager import BrowserSessionManager
from app.business.ops import mark_topic_published_from_execution
from app.logging.artifact_manager import ArtifactManager
from app.logging.event_logger import EventLogger
from app.publishers.csdn_publisher import (
    CSDNPublisher,
    CaptchaRequiredError,
    LoginExpiredError,
    PublisherError,
    ResultUncertainError,
)
from app.runner.retry_policy import RetryPolicy
from app.schemas.article_task import ArticleTask
from app.schemas.execution_result import ExecutionResult
from app.schemas.enums import ErrorType, ExecutionStage, PublishMode, TaskStatus
from app.store.task_store import TaskStore


class DebugStop(Exception):
    def __init__(self, stage: ExecutionStage) -> None:
        self.stage = stage
        super().__init__(f"debug stop at stage={stage.value}")


class ExecutionRunner:
    def __init__(self, store: TaskStore, profile_name: str | None = None, base_dir=None) -> None:
        self.store = store
        self.profile_name = profile_name
        self.base_dir = BASE_DIR if base_dir is None else base_dir
        self.logger = EventLogger()
        self.artifacts = ArtifactManager()
        self.retry_policy = RetryPolicy()

    async def run_task(
        self,
        task: ArticleTask,
        debug_stage: ExecutionStage | None = None,
    ) -> ExecutionResult:
        task.validate_publishable(allow_publish=ALLOW_PUBLISH)

        result = ExecutionResult.started(
            task_id=task.task_id or "unknown-task",
            article_id=task.article_id,
            publish_mode=task.publish_mode,
        )

        existing = self.store.get_idempotency_record(task.article_id)
        self._enforce_idempotency(task, existing)

        self.store.update_task_status(task.task_id, TaskStatus.RUNNING)
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=ExecutionStage.INIT.value,
            action="task_start",
            message="execution started",
            extra={
                "publish_mode": task.publish_mode.value,
                "debug_stage": debug_stage.value if debug_stage else None,
            },
        )

        attempt = 0
        while True:
            session = BrowserSessionManager(profile_name=self.profile_name)
            page: Page | None = None

            try:
                result.retry_count = attempt

                self.logger.info(
                    task_id=task.task_id,
                    article_id=task.article_id,
                    stage=ExecutionStage.LOAD_BROWSER_STATE.value,
                    action="browser_launch",
                    message="launching browser session",
                    extra={"attempt": attempt},
                )

                page = await session.new_page()
                final_result = await self._execute_once(task, result, page, debug_stage)
                return final_result

            except Exception as exc:
                if isinstance(exc, DebugStop):
                    screenshot_path = None
                    snapshot_path = None

                    if page is not None:
                        screenshot_path = await self.artifacts.save_screenshot(
                            page=page,
                            task_id=task.task_id,
                            stage=ExecutionStage.DEBUG_STOPPED,
                        )
                        snapshot_path = await self.artifacts.save_html_snapshot(
                            page=page,
                            task_id=task.task_id,
                            stage=ExecutionStage.DEBUG_STOPPED,
                        )

                    result.finish(
                        status=TaskStatus.DEBUG_STOPPED,
                        final_stage=ExecutionStage.DEBUG_STOPPED,
                        error_message=str(exc),
                        screenshot_path=screenshot_path,
                        snapshot_path=snapshot_path,
                    )
                    self._persist_failure(task, result, TaskStatus.DEBUG_STOPPED)
                    self.logger.info(
                        task_id=task.task_id,
                        article_id=task.article_id,
                        stage=ExecutionStage.DEBUG_STOPPED.value,
                        action="debug_stop",
                        message=str(exc),
                        extra={
                            "screenshot_path": screenshot_path,
                            "snapshot_path": snapshot_path,
                        },
                    )
                    return result

                should_retry = self.retry_policy.should_retry(exc, attempt)

                self.logger.warning(
                    task_id=task.task_id,
                    article_id=task.article_id,
                    stage=result.final_stage.value,
                    action="attempt_failed",
                    message=str(exc),
                    extra={
                        "attempt": attempt,
                        "should_retry": should_retry,
                        "exception_type": exc.__class__.__name__,
                    },
                )

                if not should_retry:
                    return await self._finalize_exception(task, result, exc, page)

                attempt += 1
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)

            finally:
                await session.close()

    async def _execute_once(
        self,
        task: ArticleTask,
        result: ExecutionResult,
        page: Page,
        debug_stage: ExecutionStage | None,
    ) -> ExecutionResult:
        publisher = CSDNPublisher(page)

        result.final_stage = ExecutionStage.OPEN_EDITOR
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="open_editor",
            message="opening csdn editor",
        )
        await publisher.validate_task(task)
        await publisher.open_editor(task)
        self._check_debug_stop(result.final_stage, debug_stage)

        result.final_stage = ExecutionStage.CHECK_LOGIN
        is_logged_in = await publisher.check_login()
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="check_login",
            message="checked login status",
            extra={"is_logged_in": is_logged_in},
        )

        if not is_logged_in:
            raise LoginExpiredError("login appears to be expired")

        if await publisher.detect_captcha():
            raise CaptchaRequiredError("captcha or security challenge detected")

        self._check_debug_stop(result.final_stage, debug_stage)

        editor_inspection = await publisher.inspect_editors()
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="inspect_editors",
            message="editor inspection snapshot",
            extra=editor_inspection,
        )

        result.final_stage = ExecutionStage.FILL_TITLE
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="fill_title",
            message="filling title",
            extra={"title_length": len(task.title)},
        )
        await publisher.fill_title(task)
        self._check_debug_stop(result.final_stage, debug_stage)

        result.final_stage = ExecutionStage.FILL_BODY
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="fill_body",
            message="filling body",
            extra={"body_length": len(task.body_markdown)},
        )
        await publisher.fill_body(task)
        self._check_debug_stop(result.final_stage, debug_stage)

        result.final_stage = ExecutionStage.FILL_METADATA
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="fill_metadata",
            message="filling metadata",
            extra={"tag_count": len(task.tags)},
        )
        await publisher.fill_metadata(task)
        self._check_debug_stop(result.final_stage, debug_stage)

        if task.publish_mode == PublishMode.DRAFT:
            result.final_stage = ExecutionStage.SAVE_DRAFT
            self.logger.info(
                task_id=task.task_id,
                article_id=task.article_id,
                stage=result.final_stage.value,
                action="save_draft",
                message="saving draft",
            )
            save_payload = await publisher.save_draft(task)
            self._check_debug_stop(result.final_stage, debug_stage)

            result.final_stage = ExecutionStage.VERIFY_RESULT
            verify_payload = await publisher.verify_result(task)
            self.logger.info(
                task_id=task.task_id,
                article_id=task.article_id,
                stage=result.final_stage.value,
                action="verify_draft_result",
                message="draft result verified",
                extra={
                    "save_payload": save_payload,
                    "verify_payload": verify_payload,
                },
            )

            result.finish(
                status=TaskStatus.SUCCESS,
                final_stage=ExecutionStage.DONE,
                draft_url=save_payload.get("draft_url") or verify_payload.get("url"),
            )
            self._persist_success(task, result)
            return result

        result.final_stage = ExecutionStage.SUBMIT_PUBLISH
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="submit_publish",
            message="submitting publish request",
        )
        publish_payload = await publisher.publish(task)
        self._check_debug_stop(result.final_stage, debug_stage)

        result.final_stage = ExecutionStage.VERIFY_RESULT
        verify_payload = await publisher.verify_result(task)
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="verify_publish_result",
            message="publish result verified",
            extra={
                "publish_payload": publish_payload,
                "verify_payload": verify_payload,
            },
        )

        article_url = publish_payload.get("article_url") or verify_payload.get("url")
        if not article_url:
            raise ResultUncertainError("publish completed but article_url is missing")

        result.finish(
            status=TaskStatus.SUCCESS,
            final_stage=ExecutionStage.DONE,
            article_url=article_url,
        )
        self._persist_success(task, result)
        return result

    async def _finalize_exception(
        self,
        task: ArticleTask,
        result: ExecutionResult,
        exc: Exception,
        page: Page | None,
    ) -> ExecutionResult:
        screenshot_path = None
        snapshot_path = None

        if page is not None:
            screenshot_path = await self.artifacts.save_screenshot(
                page=page,
                task_id=task.task_id,
                stage=result.final_stage,
            )
            snapshot_path = await self.artifacts.save_html_snapshot(
                page=page,
                task_id=task.task_id,
                stage=result.final_stage,
            )

        if isinstance(exc, LoginExpiredError):
            result.finish(
                status=TaskStatus.MANUAL_REQUIRED,
                final_stage=ExecutionStage.LOGIN_EXPIRED,
                error_type=ErrorType.MANUAL_REQUIRED,
                error_message=str(exc),
                manual_reason="login expired",
                screenshot_path=screenshot_path,
                snapshot_path=snapshot_path,
            )
            self._persist_failure(task, result, TaskStatus.MANUAL_REQUIRED)
            self.logger.error(
                task_id=task.task_id,
                article_id=task.article_id,
                stage=ExecutionStage.LOGIN_EXPIRED.value,
                action="manual_required",
                message=str(exc),
                extra={"screenshot_path": screenshot_path, "snapshot_path": snapshot_path},
            )
            return result

        if isinstance(exc, CaptchaRequiredError):
            result.finish(
                status=TaskStatus.MANUAL_REQUIRED,
                final_stage=ExecutionStage.CAPTCHA_REQUIRED,
                error_type=ErrorType.MANUAL_REQUIRED,
                error_message=str(exc),
                manual_reason="captcha required",
                screenshot_path=screenshot_path,
                snapshot_path=snapshot_path,
            )
            self._persist_failure(task, result, TaskStatus.MANUAL_REQUIRED)
            self.logger.error(
                task_id=task.task_id,
                article_id=task.article_id,
                stage=ExecutionStage.CAPTCHA_REQUIRED.value,
                action="manual_required",
                message=str(exc),
                extra={"screenshot_path": screenshot_path, "snapshot_path": snapshot_path},
            )
            return result

        if isinstance(exc, ResultUncertainError):
            result.finish(
                status=TaskStatus.UNCERTAIN,
                final_stage=ExecutionStage.RESULT_UNCERTAIN,
                error_type=ErrorType.UNCERTAIN,
                error_message=str(exc),
                screenshot_path=screenshot_path,
                snapshot_path=snapshot_path,
            )
            self._persist_failure(task, result, TaskStatus.UNCERTAIN)
            self.logger.error(
                task_id=task.task_id,
                article_id=task.article_id,
                stage=ExecutionStage.RESULT_UNCERTAIN.value,
                action="uncertain_result",
                message=str(exc),
                extra={"screenshot_path": screenshot_path, "snapshot_path": snapshot_path},
            )
            return result

        if isinstance(exc, ValueError):
            result.finish(
                status=TaskStatus.FAILED,
                final_stage=result.final_stage,
                error_type=ErrorType.FATAL,
                error_message=str(exc),
                screenshot_path=screenshot_path,
                snapshot_path=snapshot_path,
            )
            self._persist_failure(task, result, TaskStatus.FAILED)
            self.logger.error(
                task_id=task.task_id,
                article_id=task.article_id,
                stage=result.final_stage.value,
                action="validation_or_idempotency_error",
                message=str(exc),
                extra={"screenshot_path": screenshot_path, "snapshot_path": snapshot_path},
            )
            return result

        if isinstance(exc, PublisherError):
            result.finish(
                status=TaskStatus.FAILED,
                final_stage=result.final_stage,
                error_type=ErrorType.FATAL,
                error_message=str(exc),
                screenshot_path=screenshot_path,
                snapshot_path=snapshot_path,
            )
            self._persist_failure(task, result, TaskStatus.FAILED)
            self.logger.error(
                task_id=task.task_id,
                article_id=task.article_id,
                stage=result.final_stage.value,
                action="publisher_error",
                message=str(exc),
                extra={"screenshot_path": screenshot_path, "snapshot_path": snapshot_path},
            )
            return result

        result.finish(
            status=TaskStatus.FAILED,
            final_stage=result.final_stage,
            error_type=ErrorType.FATAL,
            error_message=f"unexpected error: {exc}",
            screenshot_path=screenshot_path,
            snapshot_path=snapshot_path,
        )
        self._persist_failure(task, result, TaskStatus.FAILED)
        self.logger.error(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=result.final_stage.value,
            action="unexpected_error",
            message=str(exc),
            extra={
                "exception_type": exc.__class__.__name__,
                "screenshot_path": screenshot_path,
                "snapshot_path": snapshot_path,
            },
        )
        return result

    def _persist_success(self, task: ArticleTask, result: ExecutionResult) -> None:
        self.store.update_task_status(task.task_id, TaskStatus.SUCCESS)
        self.store.insert_execution_result(result)
        self.store.upsert_idempotency_record(
            article_id=task.article_id,
            last_task_id=task.task_id,
            publish_mode=task.publish_mode,
            last_status=TaskStatus.SUCCESS,
            draft_url=result.draft_url,
            article_url=result.article_url,
        )
        if task.publish_mode == PublishMode.PUBLISH and result.article_url:
            account_profile = str(task.metadata.get("account_profile") or self.profile_name or "").strip()
            account = str(task.metadata.get("account") or task.metadata.get("account_name") or "").strip()
            if not account:
                account = {
                    "new-main": "技术小甜甜",
                    "old-traffic": "踏雪无痕老爷子",
                }.get(account_profile, "技术小甜甜")
            note = f"正式发布成功: {result.article_url}"
            mark_topic_published_from_execution(
                date=(result.ended_at or result.started_at or "")[:10],
                account=account,
                title=task.title,
                column=task.category,
                base_dir=self.base_dir,
                notes=note,
                candidate_id=str(task.metadata.get("candidate_id") or "").strip() or None,
            )
        self.logger.info(
            task_id=task.task_id,
            article_id=task.article_id,
            stage=ExecutionStage.DONE.value,
            action="task_success",
            message="execution finished successfully",
            extra={
                "draft_url": result.draft_url,
                "article_url": result.article_url,
                "retry_count": result.retry_count,
            },
        )

    def _persist_failure(
        self,
        task: ArticleTask,
        result: ExecutionResult,
        status: TaskStatus,
    ) -> None:
        self.store.update_task_status(task.task_id, status)
        self.store.insert_execution_result(result)
        self.store.upsert_idempotency_record(
            article_id=task.article_id,
            last_task_id=task.task_id,
            publish_mode=task.publish_mode,
            last_status=status,
            draft_url=result.draft_url,
            article_url=result.article_url,
        )

    def _enforce_idempotency(self, task: ArticleTask, existing: dict | None) -> None:
        if not existing:
            return

        last_status = existing.get("last_status")
        article_url = existing.get("article_url")

        if task.publish_mode == PublishMode.PUBLISH:
            if article_url and last_status == TaskStatus.SUCCESS.value:
                raise ValueError(
                    f"article_id={task.article_id} already published, blocked by idempotency"
                )

            if last_status == TaskStatus.UNCERTAIN.value:
                raise ValueError(
                    f"article_id={task.article_id} is in uncertain state, manual review required"
                )

    def _check_debug_stop(
        self,
        current_stage: ExecutionStage,
        debug_stage: ExecutionStage | None,
    ) -> None:
        if debug_stage is not None and current_stage == debug_stage:
            raise DebugStop(current_stage)
