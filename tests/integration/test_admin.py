import pytest


@pytest.mark.asyncio
async def test_requires_auth(client):
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_forbidden(client, auth_headers):
    list_resp = await client.get("/api/v1/admin/users", headers=auth_headers)
    assert list_resp.status_code == 403
    assert list_resp.json()["error"]["code"] == "forbidden"

    usage_resp = await client.get("/api/v1/admin/usage", headers=auth_headers)
    assert usage_resp.status_code == 403

    role_resp = await client.patch(
        "/api/v1/admin/users/does-not-exist/role", json={"role": "admin"}, headers=auth_headers
    )
    assert role_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_users(client, admin_auth_headers):
    resp = await client.get("/api/v1/admin/users", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] >= 1
    assert any(u["email"] == "fixture-admin@example.com" for u in body["items"])
    assert all("role" in u for u in body["items"])


@pytest.mark.asyncio
async def test_admin_can_promote_another_user(client, admin_auth_headers):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "promote-me@example.com", "password": "fixturepass1"},
    )
    users = (await client.get("/api/v1/admin/users", headers=admin_auth_headers)).json()["items"]
    target = next(u for u in users if u["email"] == "promote-me@example.com")
    assert target["role"] == "user"

    patch_resp = await client.patch(
        f"/api/v1/admin/users/{target['id']}/role",
        json={"role": "admin"},
        headers=admin_auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "admin"

    login = await client.post(
        "/api/v1/auth/login", json={"email": "promote-me@example.com", "password": "fixturepass1"}
    )
    new_admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    now_allowed = await client.get("/api/v1/admin/users", headers=new_admin_headers)
    assert now_allowed.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_change_own_role(client, admin_auth_headers):
    me = await client.get("/api/v1/auth/me", headers=admin_auth_headers)
    admin_id = me.json()["id"]

    resp = await client.patch(
        f"/api/v1/admin/users/{admin_id}/role", json={"role": "user"}, headers=admin_auth_headers
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_role_update_missing_user(client, admin_auth_headers):
    resp = await client.patch(
        "/api/v1/admin/users/does-not-exist/role",
        json={"role": "admin"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_list_usage(client, admin_auth_headers):
    resp = await client.get("/api/v1/admin/usage", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body
