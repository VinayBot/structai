import pytest
from sqlalchemy import event

from app.db import get_engine


@pytest.mark.asyncio
async def test_create_chat_and_fetch_detail(client, auth_headers):
    create = await client.post("/api/v1/chats", json={"title": "Chat 1"}, headers=auth_headers)
    assert create.status_code == 201
    chat_id = create.json()["id"]

    detail = await client.get(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == "Chat 1"
    assert detail.json()["messages"] == []


@pytest.mark.asyncio
async def test_create_chat_with_invalid_project_id(client, auth_headers):
    resp = await client.post(
        "/api/v1/chats", json={"title": "Chat", "project_id": "nope"}, headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_and_list_messages(client, auth_headers):
    create = await client.post("/api/v1/chats", json={"title": "Chat"}, headers=auth_headers)
    chat_id = create.json()["id"]

    msg = await client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"role": "user", "content": "hello there"},
        headers=auth_headers,
    )
    assert msg.status_code == 201
    assert msg.json()["content"] == "hello there"

    listing = await client.get(f"/api/v1/chats/{chat_id}/messages", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert len(listing.json()["items"]) == 1

    detail = await client.get(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    assert len(detail.json()["messages"]) == 1


@pytest.mark.asyncio
async def test_message_persists_token_usage(client, auth_headers):
    create = await client.post("/api/v1/chats", json={"title": "Chat"}, headers=auth_headers)
    chat_id = create.json()["id"]

    msg = await client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={
            "role": "assistant",
            "content": "the answer",
            "provider": "groq",
            "model": "openai/gpt-oss-20b",
            "prompt_tokens": 42,
            "completion_tokens": 17,
        },
        headers=auth_headers,
    )
    assert msg.status_code == 201
    assert msg.json()["prompt_tokens"] == 42
    assert msg.json()["completion_tokens"] == 17

    detail = await client.get(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    stored = detail.json()["messages"][0]
    assert stored["prompt_tokens"] == 42
    assert stored["completion_tokens"] == 17


@pytest.mark.asyncio
async def test_message_without_token_usage_defaults_to_null(client, auth_headers):
    """A plain user message (no provider call behind it) has no token counts at
    all - null, not 0, since 0 would misleadingly claim "a call happened and used
    no tokens" rather than "no call happened"."""
    create = await client.post("/api/v1/chats", json={"title": "Chat"}, headers=auth_headers)
    chat_id = create.json()["id"]

    msg = await client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"role": "user", "content": "hello"},
        headers=auth_headers,
    )
    assert msg.status_code == 201
    assert msg.json()["prompt_tokens"] is None
    assert msg.json()["completion_tokens"] is None


@pytest.mark.asyncio
async def test_list_chats_filtered_by_project(client, auth_headers):
    project = await client.post("/api/v1/projects", json={"name": "P"}, headers=auth_headers)
    project_id = project.json()["id"]

    await client.post(
        "/api/v1/chats",
        json={"title": "In project", "project_id": project_id},
        headers=auth_headers,
    )
    await client.post("/api/v1/chats", json={"title": "No project"}, headers=auth_headers)

    filtered = await client.get(f"/api/v1/chats?project_id={project_id}", headers=auth_headers)
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "In project"


@pytest.mark.asyncio
async def test_delete_chat(client, auth_headers):
    create = await client.post("/api/v1/chats", json={"title": "Gone soon"}, headers=auth_headers)
    chat_id = create.json()["id"]

    delete = await client.delete(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after = await client.get(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_message_to_nonexistent_chat(client, auth_headers):
    resp = await client.post(
        "/api/v1/chats/does-not-exist/messages",
        json={"role": "user", "content": "hi"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_not_visible_to_other_user(client, auth_headers):
    create = await client.post("/api/v1/chats", json={"title": "Private"}, headers=auth_headers)
    chat_id = create.json()["id"]

    await client.post(
        "/api/v1/auth/register", json={"email": "chat-other@example.com", "password": "otherpass1"}
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "chat-other@example.com", "password": "otherpass1"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get(f"/api/v1/chats/{chat_id}", headers=other_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_detail_pagination_and_response_shape_unaffected(client, auth_headers):
    """Same assertions test_add_and_list_messages already made about the detail
    route's response shape - re-stated here to anchor the before/after comparison in
    the query-count test below to a response that's known to still be correct."""
    create = await client.post("/api/v1/chats", json={"title": "Shape check"}, headers=auth_headers)
    chat_id = create.json()["id"]
    for content in ("first", "second", "third"):
        await client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={"role": "user", "content": content},
            headers=auth_headers,
        )

    detail = await client.get(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert [m["content"] for m in body["messages"]] == ["first", "second", "third"]
    assert body["id"] == chat_id


@pytest.mark.asyncio
async def test_chat_detail_route_no_longer_issues_a_redundant_chat_lookup_or_count(
    client, auth_headers
):
    """Before this fix, GET /chats/{id} ran 5 SELECTs for this exact scenario: the
    auth lookup, the route's own chat lookup, a *second* chat lookup buried inside
    list_messages (which always re-verified ownership from scratch), an unconditional
    COUNT(*) that the detail view never uses, and finally the messages SELECT itself.
    It should now run exactly 3: auth, chat, messages - no duplicate chat lookup, no
    COUNT(*)."""
    create = await client.post("/api/v1/chats", json={"title": "Query count"}, headers=auth_headers)
    chat_id = create.json()["id"]
    await client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"role": "user", "content": "hello"},
        headers=auth_headers,
    )

    queries: list[str] = []
    engine = get_engine()

    def _record(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement.strip())

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        detail = await client.get(f"/api/v1/chats/{chat_id}", headers=auth_headers)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)

    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 1

    selects = [q for q in queries if q.upper().startswith("SELECT")]
    chat_lookups = [q for q in selects if "FROM chats" in q]
    count_queries = [q for q in selects if "count(" in q.lower()]

    assert len(selects) == 3, f"expected exactly 3 SELECTs, got {len(selects)}:\n" + "\n".join(
        selects
    )
    assert len(chat_lookups) == 1, "chat should be looked up exactly once, not re-queried"
    assert count_queries == [], "the detail route doesn't use a total - no COUNT(*) expected"
