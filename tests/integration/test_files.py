import os

import pytest


@pytest.mark.asyncio
async def test_upload_and_fetch_file(client, auth_headers):
    files = {"file": ("note.txt", b"hello world", "text/plain")}
    upload = await client.post("/files", files=files, headers=auth_headers)
    assert upload.status_code == 201
    body = upload.json()
    assert body["filename"] == "note.txt"
    assert body["size_bytes"] == len(b"hello world")

    get_one = await client.get(f"/files/{body['id']}", headers=auth_headers)
    assert get_one.status_code == 200
    assert get_one.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_list_files(client, auth_headers):
    files = {"file": ("a.txt", b"abc", "text/plain")}
    await client.post("/files", files=files, headers=auth_headers)

    listing = await client.get("/files", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


@pytest.mark.asyncio
async def test_oversize_upload_rejected(client, auth_headers, monkeypatch):
    os.environ["MAX_UPLOAD_SIZE_BYTES"] = "10"
    from app.config import get_settings

    get_settings.cache_clear()

    files = {"file": ("big.txt", b"this payload is far larger than ten bytes", "text/plain")}
    resp = await client.post("/files", files=files, headers=auth_headers)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"

    del os.environ["MAX_UPLOAD_SIZE_BYTES"]


@pytest.mark.asyncio
async def test_delete_file(client, auth_headers):
    files = {"file": ("gone.txt", b"bye", "text/plain")}
    upload = await client.post("/files", files=files, headers=auth_headers)
    file_id = upload.json()["id"]

    delete = await client.delete(f"/files/{file_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after = await client.get(f"/files/{file_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_file_not_visible_to_other_user(client, auth_headers):
    files = {"file": ("secret.txt", b"shh", "text/plain")}
    upload = await client.post("/files", files=files, headers=auth_headers)
    file_id = upload.json()["id"]

    await client.post(
        "/auth/register", json={"email": "other2@example.com", "password": "otherpass1"}
    )
    login = await client.post(
        "/auth/login", json={"email": "other2@example.com", "password": "otherpass1"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get(f"/files/{file_id}", headers=other_headers)
    assert resp.status_code == 404
