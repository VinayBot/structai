import pytest


@pytest.mark.asyncio
async def test_create_and_list_projects(client, auth_headers):
    create = await client.post("/projects", json={"name": "My Project"}, headers=auth_headers)
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "My Project"
    assert "id" in body

    listing = await client.get("/projects", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


@pytest.mark.asyncio
async def test_get_project_not_found(client, auth_headers):
    resp = await client.get("/projects/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_delete_project(client, auth_headers):
    create = await client.post("/projects", json={"name": "Temp"}, headers=auth_headers)
    project_id = create.json()["id"]

    delete = await client.delete(f"/projects/{project_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after = await client.get(f"/projects/{project_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_project_not_visible_to_other_user(client, auth_headers):
    create = await client.post("/projects", json={"name": "Mine"}, headers=auth_headers)
    project_id = create.json()["id"]

    await client.post(
        "/auth/register", json={"email": "other@example.com", "password": "otherpass1"}
    )
    login = await client.post(
        "/auth/login", json={"email": "other@example.com", "password": "otherpass1"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get(f"/projects/{project_id}", headers=other_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_requires_auth(client):
    resp = await client.get("/projects")
    assert resp.status_code == 401
