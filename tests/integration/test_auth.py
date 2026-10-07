import app.guardrails.email as email_guard
from app.config import get_settings
from app.core.errors import OAuthError
from app.services import github_oauth_client
from app.services.github_oauth_client import GithubProfile


async def _register(client, email="alice@example.com", password="password123"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


async def test_register_creates_user(client):
    resp = await _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_conflict(client):
    await _register(client)
    resp = await _register(client)
    assert resp.status_code == 409


async def test_register_disposable_email_rejected(client):
    resp = await _register(client, email="bob@mailinator.com")
    assert resp.status_code == 409


async def test_register_weak_password_rejected(client):
    resp = await _register(client, password="nodigits")
    assert resp.status_code == 422


async def test_register_short_password_rejected(client):
    resp = await _register(client, password="a1")
    assert resp.status_code == 422


async def test_register_typo_domain_rejected_with_suggestion(client):
    resp = await _register(client, email="alice@gmial.com")
    assert resp.status_code == 422
    body = resp.json()["error"]
    assert body["code"] == "invalid_email_domain"
    assert body["suggestion"] == "alice@gmail.com"


async def test_register_unreachable_domain_rejected(client, monkeypatch):
    async def fake_unreachable(domain, timeout):
        return "unreachable"

    monkeypatch.setenv("EMAIL_CHECK_MX", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(email_guard, "_check_mx", fake_unreachable)

    resp = await _register(client, email="alice@genuinely-nonexistent-domain-xyz.example")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "email_domain_unreachable"


async def test_register_respects_email_check_mx_setting_disabled(client, monkeypatch):
    """The test suite runs with EMAIL_CHECK_MX=false (see conftest.py) specifically so it
    never depends on live DNS - this proves that setting, not luck, is what lets a domain
    which would otherwise fail MX through unblocked."""

    async def fake_unreachable(domain, timeout):
        return "unreachable"

    monkeypatch.setattr(email_guard, "_check_mx", fake_unreachable)
    resp = await _register(client, email="charlie@genuinely-nonexistent-domain-xyz.example")
    assert resp.status_code == 201


async def test_check_email_endpoint_accepts_valid_address_without_creating_account(client):
    resp = await client.post("/api/v1/auth/check-email", json={"email": "newuser@example.com"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True

    login = await client.post(
        "/api/v1/auth/login", json={"email": "newuser@example.com", "password": "whatever123"}
    )
    assert login.status_code == 401


async def test_check_email_endpoint_flags_disposable_domain(client):
    resp = await client.post("/api/v1/auth/check-email", json={"email": "bob@mailinator.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["message"]


async def test_check_email_endpoint_flags_typo_with_suggestion(client):
    resp = await client.post("/api/v1/auth/check-email", json={"email": "user@gmial.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["suggestion"] == "user@gmail.com"


async def test_check_email_endpoint_rejects_malformed_syntax_at_the_schema_level(client):
    resp = await client.post("/api/v1/auth/check-email", json={"email": "not-an-email"})
    assert resp.status_code == 422


async def test_login_success_returns_tokens(client):
    await _register(client)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_wrong_password_401(client):
    await _register(client)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "wrongpass1"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email_401(client):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_valid_token_returns_user(client):
    await _register(client)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    access_token = login.json()["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


async def test_me_rejects_refresh_token(client):
    await _register(client)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    refresh_token = login.json()["refresh_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401


async def test_refresh_rotates_tokens_and_old_refresh_fails(client):
    await _register(client)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    old_refresh = login.json()["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != old_refresh

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await _register(client)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401


def _configure_github(monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()


def _mock_github_identity(monkeypatch, *, subject="12345", email="octocat@example.com"):
    async def _fake_exchange(**_kwargs):
        return "fake-github-access-token"

    async def _fake_fetch(_token):
        return GithubProfile(subject=subject, email=email, username="octocat")

    monkeypatch.setattr(github_oauth_client, "exchange_code_for_token", _fake_exchange)
    monkeypatch.setattr(github_oauth_client, "fetch_profile", _fake_fetch)


async def test_github_login_not_configured_returns_503(client):
    resp = await client.get("/api/v1/auth/github/login?state=abcdefgh")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "service_unavailable"


async def test_github_login_returns_authorize_url(client, monkeypatch):
    _configure_github(monkeypatch)
    resp = await client.get("/api/v1/auth/github/login?state=abcdefgh")
    assert resp.status_code == 200
    url = resp.json()["authorize_url"]
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=test-client-id" in url
    assert "state=abcdefgh" in url


async def test_github_callback_not_configured_returns_503(client):
    resp = await client.post("/api/v1/auth/github/callback", json={"code": "whatever"})
    assert resp.status_code == 503


async def test_github_callback_creates_new_user(client, monkeypatch):
    _configure_github(monkeypatch)
    _mock_github_identity(monkeypatch, subject="111", email="newcomer@example.com")

    resp = await client.post("/api/v1/auth/github/callback", json={"code": "good-code"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.json()["email"] == "newcomer@example.com"
    assert me.json()["role"] == "user"


async def test_github_callback_reuses_same_user_on_second_login(client, monkeypatch):
    _configure_github(monkeypatch)
    _mock_github_identity(monkeypatch, subject="222", email="regular@example.com")

    first = await client.post("/api/v1/auth/github/callback", json={"code": "code-1"})
    second = await client.post("/api/v1/auth/github/callback", json={"code": "code-2"})
    assert first.status_code == 200 and second.status_code == 200

    first_id = (
        await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {first.json()['access_token']}"},
        )
    ).json()["id"]
    second_id = (
        await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {second.json()['access_token']}"},
        )
    ).json()["id"]
    assert first_id == second_id


async def test_github_callback_links_existing_password_account_by_email(client, monkeypatch):
    await _register(client, email="shared@example.com", password="password123")

    _configure_github(monkeypatch)
    _mock_github_identity(monkeypatch, subject="333", email="shared@example.com")

    resp = await client.post("/api/v1/auth/github/callback", json={"code": "good-code"})
    assert resp.status_code == 200

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"}
    )
    assert me.json()["email"] == "shared@example.com"

    # The original password still works - linking didn't disturb it.
    password_login = await client.post(
        "/api/v1/auth/login", json={"email": "shared@example.com", "password": "password123"}
    )
    assert password_login.status_code == 200


async def test_github_callback_upstream_failure_returns_502(client, monkeypatch):
    _configure_github(monkeypatch)

    async def _failing_exchange(**_kwargs):
        raise OAuthError("github rejected the authorization code")

    monkeypatch.setattr(github_oauth_client, "exchange_code_for_token", _failing_exchange)

    resp = await client.post("/api/v1/auth/github/callback", json={"code": "bad-code"})
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "oauth_failed"
