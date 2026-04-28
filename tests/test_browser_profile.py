from app.config import DEFAULT_BROWSER_PROFILE, get_browser_profile_dir, normalize_profile_name


def test_normalize_profile_name_uses_default_for_empty_input():
    assert normalize_profile_name("") == DEFAULT_BROWSER_PROFILE


def test_normalize_profile_name_replaces_unsafe_characters():
    assert normalize_profile_name("my account/01") == "my-account-01"


def test_get_browser_profile_dir_uses_normalized_name():
    path = get_browser_profile_dir("team account")
    assert path.name == "team-account"
