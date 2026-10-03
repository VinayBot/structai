"""Audit local tooling and model-provider availability. Never prints secret values."""

import shutil
import subprocess
import sys

import httpx

from app.config import get_settings


def check_command(name: str) -> str:
    path = shutil.which(name)
    return f"OK ({path})" if path else "MISSING"


def check_docker_daemon() -> str:
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=True)
        return "OK (daemon reachable)"
    except Exception:
        return "MISSING (daemon not reachable)"


def check_ollama(base_url: str) -> str:
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=3)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return f"OK ({len(models)} model(s): {', '.join(models) or 'none'})"
    except Exception as exc:
        return f"UNREACHABLE ({exc})"


def check_groq(api_key: str) -> str:
    if not api_key:
        return "SKIPPED (GROQ_API_KEY not set)"
    try:
        resp = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        resp.raise_for_status()
        count = len(resp.json().get("data", []))
        return f"OK ({count} model(s) visible)"
    except Exception as exc:
        return f"ERROR ({exc})"


def main() -> int:
    settings = get_settings()

    print("=== StructAI environment check ===")
    print(f"docker binary:    {check_command('docker')}")
    print(f"docker daemon:    {check_docker_daemon()}")
    print(f"docker-compose:   {check_command('docker-compose')}")
    print(f"node:             {check_command('node')}")
    print(f"npm:              {check_command('npm')}")
    print(f"ollama:           {check_ollama(settings.ollama_base_url)}")
    print(f"groq:             {check_groq(settings.groq_api_key)}")
    print(f"hf_token set:     {'yes' if settings.hf_token else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
