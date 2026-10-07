"""Thin async wrapper around GitHub's OAuth + REST API - the two outbound HTTP
calls behind the GitHub login flow, kept separate from auth_service's
find-or-create logic so tests can mock them without faking httpx itself.
Mirrors the pattern in app/gateway/providers/*.py, applied to a third-party
identity API instead of a model API."""

from dataclasses import dataclass

import httpx

from app.core.errors import OAuthError

_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_EMAILS_URL = "https://api.github.com/user/emails"


@dataclass
class GithubProfile:
    subject: str
    email: str
    username: str


async def exchange_code_for_token(
    *, code: str, client_id: str, client_secret: str, redirect_uri: str
) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthError(f"github token exchange failed: {exc}") from exc

    token = data.get("access_token")
    if not token:
        raise OAuthError(data.get("error_description") or "github rejected the authorization code")
    return token


async def fetch_profile(github_access_token: str) -> GithubProfile:
    headers = {
        "Authorization": f"Bearer {github_access_token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            user_resp = await client.get(_USER_URL, headers=headers)
            user_resp.raise_for_status()
            user = user_resp.json()

            email = user.get("email")
            if not email:
                emails_resp = await client.get(_EMAILS_URL, headers=headers)
                emails_resp.raise_for_status()
                email = _pick_best_email(emails_resp.json())
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise OAuthError(f"github profile fetch failed: {exc}") from exc

    if not email:
        raise OAuthError("github account has no verified email address to sign in with")

    return GithubProfile(subject=str(user["id"]), email=email, username=user.get("login", ""))


def _pick_best_email(emails: list[dict]) -> str | None:
    """Prefers the primary+verified address; falls back to any verified one -
    GitHub lets a user mark a non-primary address verified too."""
    verified = [e for e in emails if e.get("verified")]
    primary = next((e for e in verified if e.get("primary")), None)
    chosen = primary or (verified[0] if verified else None)
    return chosen["email"] if chosen else None
