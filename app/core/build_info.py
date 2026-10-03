import subprocess
import time
from functools import lru_cache

from app.config import get_settings

_PROCESS_STARTED_AT = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _detect_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=True,
        )
    except Exception:
        return None
    commit = result.stdout.strip()
    return commit or None


@lru_cache
def get_build_info() -> tuple[str, str]:
    settings = get_settings()
    commit = settings.git_commit or _detect_git_commit() or "unknown"
    build_time = settings.build_time or _PROCESS_STARTED_AT
    return commit, build_time


def reset_build_info_cache() -> None:
    get_build_info.cache_clear()
