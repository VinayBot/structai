import httpx
import pytest

from app.core.errors import OAuthError
from app.services import github_oauth_client as goc


@pytest.fixture
def install_github_transport(monkeypatch):
    """Makes every httpx.AsyncClient() constructed inside github_oauth_client use
    a MockTransport routed by `handler`, instead of touching the real network."""

    def _install(handler):
        real_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    return _install


async def test_exchange_code_for_token_success(install_github_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/login/oauth/access_token"
        return httpx.Response(200, json={"access_token": "gho_fake", "token_type": "bearer"})

    install_github_transport(handler)
    token = await goc.exchange_code_for_token(
        code="abc", client_id="id", client_secret="secret", redirect_uri="http://cb"
    )
    assert token == "gho_fake"


async def test_exchange_code_for_token_rejected_code(install_github_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": "bad_verification_code", "error_description": "code expired"},
        )

    install_github_transport(handler)
    with pytest.raises(OAuthError, match="code expired"):
        await goc.exchange_code_for_token(
            code="abc", client_id="id", client_secret="secret", redirect_uri="http://cb"
        )


async def test_exchange_code_for_token_http_error(install_github_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    install_github_transport(handler)
    with pytest.raises(OAuthError):
        await goc.exchange_code_for_token(
            code="abc", client_id="id", client_secret="secret", redirect_uri="http://cb"
        )


async def test_fetch_profile_with_public_email(install_github_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/user"
        assert request.headers["Authorization"] == "Bearer gho_fake"
        return httpx.Response(200, json={"id": 42, "login": "octocat", "email": "octo@example.com"})

    install_github_transport(handler)
    profile = await goc.fetch_profile("gho_fake")
    assert profile == goc.GithubProfile(subject="42", email="octo@example.com", username="octocat")


async def test_fetch_profile_falls_back_to_emails_endpoint_when_private(install_github_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 7, "login": "shy", "email": None})
        assert request.url.path == "/user/emails"
        return httpx.Response(
            200,
            json=[
                {"email": "secondary@example.com", "primary": False, "verified": True},
                {"email": "primary@example.com", "primary": True, "verified": True},
            ],
        )

    install_github_transport(handler)
    profile = await goc.fetch_profile("gho_fake")
    assert profile.email == "primary@example.com"


async def test_fetch_profile_no_verified_email_raises(install_github_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 7, "login": "shy", "email": None})
        return httpx.Response(200, json=[{"email": "unverified@example.com", "verified": False}])

    install_github_transport(handler)
    with pytest.raises(OAuthError, match="no verified email"):
        await goc.fetch_profile("gho_fake")


async def test_fetch_profile_http_error(install_github_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    install_github_transport(handler)
    with pytest.raises(OAuthError):
        await goc.fetch_profile("expired-token")
