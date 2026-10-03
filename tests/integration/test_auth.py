import app.guardrails.email as email_guard
from app.config import get_settings


async def _register(client, email="alice@example.com", password="password123"):
    return await client.post("/auth/register", json={"email": email, "password": password})


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
    resp = await client.post("/auth/check-email", json={"email": "newuser@example.com"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True

    login = await client.post(
        "/auth/login", json={"email": "newuser@example.com", "password": "whatever123"}
    )
    assert login.status_code == 401


async def test_check_email_endpoint_flags_disposable_domain(client):
    resp = await client.post("/auth/check-email", json={"email": "bob@mailinator.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["message"]


async def test_check_email_endpoint_flags_typo_with_suggestion(client):
    resp = await client.post("/auth/check-email", json={"email": "user@gmial.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["suggestion"] == "user@gmail.com"


async def test_check_email_endpoint_rejects_malformed_syntax_at_the_schema_level(client):
    resp = await client.post("/auth/check-email", json={"email": "not-an-email"})
    assert resp.status_code == 422


async def test_login_success_returns_tokens(client):
    await _register(client)
    resp = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_wrong_password_401(client):
    await _register(client)
    resp = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "wrongpass1"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email_401(client):
    resp = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_valid_token_returns_user(client):
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    access_token = login.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


async def test_me_rejects_refresh_token(client):
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    refresh_token = login.json()["refresh_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401


async def test_refresh_rotates_tokens_and_old_refresh_fails(client):
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    old_refresh = login.json()["refresh_token"]

    refreshed = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != old_refresh

    reused = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    reused = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401
