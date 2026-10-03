async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["git_commit"], str) and body["git_commit"]
    assert isinstance(body["build_time"], str) and body["build_time"]


async def test_ready_reflects_db(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["db"] is True


async def test_health_sets_request_id_header(client):
    resp = await client.get("/health")
    assert "x-request-id" in resp.headers
