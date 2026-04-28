from app.publishers.csdn_publisher import (
    CaptchaRequiredError,
    EditorNotReadyError,
    LoginExpiredError,
    PublisherError,
    ResultUncertainError,
)
from app.runner.retry_policy import RetryPolicy


def test_retry_policy_retries_editor_not_ready():
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry(EditorNotReadyError("editor did not become ready"), attempt=0) is True


def test_retry_policy_does_not_retry_captcha():
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry(CaptchaRequiredError("captcha"), attempt=0) is False


def test_retry_policy_does_not_retry_login_expired():
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry(LoginExpiredError("login expired"), attempt=0) is False


def test_retry_policy_does_not_retry_uncertain():
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry(ResultUncertainError("uncertain"), attempt=0) is False


def test_retry_policy_retries_timeout_like_publisher_error():
    policy = RetryPolicy(max_retries=2)
    exc = PublisherError("network timeout while waiting for page")
    assert policy.should_retry(exc, attempt=0) is True


def test_retry_policy_stops_when_attempt_limit_reached():
    policy = RetryPolicy(max_retries=1)
    exc = EditorNotReadyError("editor did not become ready")
    assert policy.should_retry(exc, attempt=1) is False
