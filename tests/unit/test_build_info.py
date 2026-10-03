import os

from app.config import get_settings
from app.core.build_info import get_build_info, reset_build_info_cache


def test_returns_non_empty_commit_and_build_time():
    commit, build_time = get_build_info()
    assert isinstance(commit, str) and commit
    assert isinstance(build_time, str) and build_time


def test_settings_override_wins_over_git_detection():
    os.environ["GIT_COMMIT"] = "deadbeef"
    os.environ["BUILD_TIME"] = "2026-01-01T00:00:00Z"
    get_settings.cache_clear()
    reset_build_info_cache()
    try:
        commit, build_time = get_build_info()
        assert commit == "deadbeef"
        assert build_time == "2026-01-01T00:00:00Z"
    finally:
        del os.environ["GIT_COMMIT"]
        del os.environ["BUILD_TIME"]
        get_settings.cache_clear()
        reset_build_info_cache()


def test_falls_back_to_unknown_when_git_detection_fails(monkeypatch):
    from app.core import build_info as build_info_module

    monkeypatch.setattr(build_info_module, "_detect_git_commit", lambda: None)
    reset_build_info_cache()

    commit, _ = get_build_info()
    assert commit == "unknown"
