from __future__ import annotations

from enum import Enum


class PublishMode(str, Enum):
    DRAFT = "draft"
    PUBLISH = "publish"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"
    DEBUG_STOPPED = "debug_stopped"


class ErrorType(str, Enum):
    RETRYABLE = "retryable"
    MANUAL_REQUIRED = "manual_required"
    UNCERTAIN = "uncertain"
    FATAL = "fatal"


class ExecutionStage(str, Enum):
    INIT = "init"
    LOAD_BROWSER_STATE = "load_browser_state"
    OPEN_EDITOR = "open_editor"
    CHECK_LOGIN = "check_login"
    FILL_TITLE = "fill_title"
    FILL_BODY = "fill_body"
    FILL_METADATA = "fill_metadata"
    SAVE_DRAFT = "save_draft"
    SUBMIT_PUBLISH = "submit_publish"
    VERIFY_RESULT = "verify_result"
    PERSIST_RESULT = "persist_result"
    DONE = "done"

    LOGIN_EXPIRED = "login_expired"
    EDITOR_NOT_READY = "editor_not_ready"
    ELEMENT_NOT_FOUND = "element_not_found"
    CAPTCHA_REQUIRED = "captcha_required"
    NETWORK_TIMEOUT = "network_timeout"
    RESULT_UNCERTAIN = "result_uncertain"
    DEBUG_STOPPED = "debug_stopped"
