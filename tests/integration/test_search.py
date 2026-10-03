import pytest


@pytest.mark.asyncio
async def test_search_finds_matching_chat_title(client, auth_headers):
    await client.post("/chats", json={"title": "Trip to Japan"}, headers=auth_headers)
    await client.post("/chats", json={"title": "Grocery list"}, headers=auth_headers)

    resp = await client.get("/search?q=japan", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["chats"]) == 1
    assert body["chats"][0]["title"] == "Trip to Japan"


@pytest.mark.asyncio
async def test_search_finds_matching_message_content(client, auth_headers):
    create = await client.post("/chats", json={"title": "Chat"}, headers=auth_headers)
    chat_id = create.json()["id"]
    await client.post(
        f"/chats/{chat_id}/messages",
        json={"role": "user", "content": "what is the capital of Peru"},
        headers=auth_headers,
    )

    resp = await client.get("/search?q=peru", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["messages"]) == 1
    assert "Peru" in body["messages"][0]["content"]


@pytest.mark.asyncio
async def test_search_does_not_leak_other_users_data(client, auth_headers):
    await client.post("/chats", json={"title": "Private matter"}, headers=auth_headers)

    await client.post(
        "/auth/register", json={"email": "searcher@example.com", "password": "searchpass1"}
    )
    login = await client.post(
        "/auth/login", json={"email": "searcher@example.com", "password": "searchpass1"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/search?q=private", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json()["chats"] == []


@pytest.mark.asyncio
async def test_search_requires_query(client, auth_headers):
    resp = await client.get("/search?q=", headers=auth_headers)
    assert resp.status_code == 422
