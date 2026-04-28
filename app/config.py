from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

TASK_DIR = DATA_DIR / "tasks"
PENDING_TASK_DIR = TASK_DIR / "pending"
PROCESSED_TASK_DIR = TASK_DIR / "processed"

LOG_DIR = DATA_DIR / "logs"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
BROWSER_STATE_DIR = DATA_DIR / "browser_state"
BROWSER_PROFILES_DIR = BROWSER_STATE_DIR / "profiles"

DB_PATH = DATA_DIR / "app.db"

HEADLESS = False
BROWSER_CHANNEL = "chromium"
DEFAULT_BROWSER_PROFILE = "default"
USER_DATA_DIR = BROWSER_PROFILES_DIR / DEFAULT_BROWSER_PROFILE
STORAGE_STATE_PATH = BROWSER_STATE_DIR / "storage_state.json"

CSDN_EDITOR_URL = "https://editor.csdn.net/md/"
CSDN_ARTICLE_LIST_URL = "https://mp.csdn.net/mp_blog/manage/article"

ELEMENT_TIMEOUT_MS = 10_000
PAGE_TIMEOUT_MS = 20_000
RESULT_VERIFY_TIMEOUT_MS = 10_000

MAX_RETRIES = 1
RETRY_BACKOFF_SECONDS = 2

ALLOW_PUBLISH = False
STOP_ON_CAPTCHA = True
SAVE_HTML_SNAPSHOT_ON_ERROR = True


def normalize_profile_name(profile_name: str | None) -> str:
    raw = (profile_name or DEFAULT_BROWSER_PROFILE).strip()
    if not raw:
        return DEFAULT_BROWSER_PROFILE

    cleaned = []
    for ch in raw:
        if ch.isalnum() or ch in {"-", "_", "."}:
            cleaned.append(ch)
        else:
            cleaned.append("-")

    normalized = "".join(cleaned).strip("-_.")
    return normalized or DEFAULT_BROWSER_PROFILE


def get_browser_profile_dir(profile_name: str | None = None) -> Path:
    normalized = normalize_profile_name(profile_name)
    return BROWSER_PROFILES_DIR / normalized


def ensure_directories() -> None:
    dirs = [
        DATA_DIR,
        TASK_DIR,
        PENDING_TASK_DIR,
        PROCESSED_TASK_DIR,
        LOG_DIR,
        SCREENSHOT_DIR,
        SNAPSHOT_DIR,
        BROWSER_STATE_DIR,
        BROWSER_PROFILES_DIR,
        USER_DATA_DIR,
    ]
    for path in dirs:
        path.mkdir(parents=True, exist_ok=True)
