import pytest


@pytest.mark.asyncio
async def test_validate_requires_auth(client):
    resp = await client.post(
        "/api/v1/schemas/validate", json={"fields": [{"name": "x", "type": "string"}]}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_validate_returns_json_schema(client, auth_headers):
    resp = await client.post(
        "/api/v1/schemas/validate",
        json={
            "fields": [
                {"name": "title", "type": "string"},
                {"name": "count", "type": "integer"},
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert "title" in body["json_schema"]["properties"]
    assert "count" in body["json_schema"]["properties"]


@pytest.mark.asyncio
async def test_validate_rejects_bad_field_type(client, auth_headers):
    resp = await client.post(
        "/api/v1/schemas/validate",
        json={"fields": [{"name": "title", "type": "not_a_type"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_validate_response_matches_schema_validate_response_shape(client, auth_headers):
    resp = await client.post(
        "/api/v1/schemas/validate",
        json={"fields": [{"name": "title", "type": "string"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"valid", "json_schema"}
    assert isinstance(body["valid"], bool)
    assert isinstance(body["json_schema"], dict)
