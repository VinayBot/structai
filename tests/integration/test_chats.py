import pytest


@pytest.mark.asyncio
async def test_create_chat_and_fetch_detail(client, auth_headers):
    create = await client.post("/chats", json={"title": "Chat 1"}, headers=auth_headers)
    assert create.status_code == 201
    chat_id = create.json()["id"]

    detail = await client.get(f"/chats/{chat_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == "Chat 1"
    assert detail.json()["messages"] == []


@pytest.mark.asyncio
async def test_create_chat_with_invalid_project_id(client, auth_headers):
    resp = await client.post(
        "/chats", json={"title": "Chat", "project_id": "nope"}, headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_and_list_messages(client, auth_headers):
    create = await client.post("/chats", json={"title": "Chat"}, headers=auth_headers)
    chat_id = create.json()["id"]

    msg = await client.post(
        f"/chats/{chat_id}/messages",
        json={"role": "user", "content": "hello there"},
        headers=auth_headers,
    )
    assert msg.status_code == 201
    assert msg.json()["content"] == "hello there"

    listing = await client.get(f"/chats/{chat_id}/messages", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    detail = await client.get(f"/chats/{chat_id}", headers=auth_headers)
    assert len(detail.json()["messages"]) == 1


@pytest.mark.asyncio
async def test_list_chats_filtered_by_project(client, auth_headers):
    project = await client.post("/projects", json={"name": "P"}, headers=auth_headers)
    project_id = project.json()["id"]

    await client.post(
        "/chats",
        json={"title": "In project", "project_id": project_id},
        headers=auth_headers,
    )
    await client.post("/chats", json={"title": "No project"}, headers=auth_headers)

    filtered = await client.get(f"/chats?project_id={project_id}", headers=auth_headers)
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["title"] == "In project"


@pytest.mark.asyncio
async def test_delete_chat(client, auth_headers):
    create = await client.post("/chats", json={"title": "Gone soon"}, headers=auth_headers)
    chat_id = create.json()["id"]

    delete = await client.delete(f"/chats/{chat_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after = await client.get(f"/chats/{chat_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_message_to_nonexistent_chat(client, auth_headers):
    resp = await client.post(
        "/chats/does-not-exist/messages",
        json={"role": "user", "content": "hi"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
