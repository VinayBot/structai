import os
from pathlib import Path

import pytest

from app.config import get_settings


def _leftover_temp_files() -> list[Path]:
    return list(Path(get_settings().upload_dir).rglob(".tmp-*"))


@pytest.mark.asyncio
async def test_upload_and_fetch_file(client, auth_headers):
    files = {"file": ("note.txt", b"hello world", "text/plain")}
    upload = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert upload.status_code == 201
    body = upload.json()
    assert body["filename"] == "note.txt"
    assert body["size_bytes"] == len(b"hello world")

    get_one = await client.get(f"/api/v1/files/{body['id']}", headers=auth_headers)
    assert get_one.status_code == 200
    assert get_one.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_list_files(client, auth_headers):
    files = {"file": ("a.txt", b"abc", "text/plain")}
    await client.post("/api/v1/files", files=files, headers=auth_headers)

    listing = await client.get("/api/v1/files", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert len(listing.json()["items"]) == 1


@pytest.mark.asyncio
async def test_oversize_upload_rejected(client, auth_headers, monkeypatch):
    os.environ["MAX_UPLOAD_SIZE_BYTES"] = "10"
    get_settings.cache_clear()

    files = {"file": ("big.txt", b"this payload is far larger than ten bytes", "text/plain")}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"
    assert _leftover_temp_files() == []

    del os.environ["MAX_UPLOAD_SIZE_BYTES"]


@pytest.mark.asyncio
async def test_upload_exactly_at_limit_is_accepted(client, auth_headers):
    os.environ["MAX_UPLOAD_SIZE_BYTES"] = "11"
    get_settings.cache_clear()

    files = {"file": ("exact.txt", b"12345678901", "text/plain")}  # exactly 11 bytes
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["size_bytes"] == 11

    del os.environ["MAX_UPLOAD_SIZE_BYTES"]


@pytest.mark.asyncio
async def test_upload_one_byte_over_limit_is_rejected(client, auth_headers):
    os.environ["MAX_UPLOAD_SIZE_BYTES"] = "11"
    get_settings.cache_clear()

    files = {"file": ("over.txt", b"123456789012", "text/plain")}  # 12 bytes
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 413
    assert _leftover_temp_files() == []

    del os.environ["MAX_UPLOAD_SIZE_BYTES"]


@pytest.mark.asyncio
async def test_disallowed_content_type_rejected(client, auth_headers):
    files = {"file": ("script.sh", b"#!/bin/sh\necho hi", "application/x-sh")}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_media_type"
    assert _leftover_temp_files() == []


@pytest.mark.asyncio
async def test_upload_rejects_spoofed_image_content_type(client, auth_headers):
    """The Content-Type header is client-supplied and trivially spoofable - a
    renamed shell script claiming to be a PNG must still be rejected."""
    files = {"file": ("totally-a-photo.png", b"#!/bin/sh\necho hi", "image/png")}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_media_type"
    assert _leftover_temp_files() == []


@pytest.mark.asyncio
async def test_upload_rejects_malformed_json_claiming_json_type(client, auth_headers):
    files = {"file": ("data.json", b"{not valid json", "application/json")}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 415
    assert _leftover_temp_files() == []


@pytest.mark.asyncio
async def test_upload_rejects_invalid_utf8_claiming_text_type(client, auth_headers):
    files = {"file": ("note.txt", b"\xff\xfe\x00\x01not-utf8", "text/plain")}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 415
    assert _leftover_temp_files() == []


@pytest.mark.asyncio
async def test_upload_accepts_content_with_a_real_png_signature(client, auth_headers):
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-the-signature-is-real"
    files = {"file": ("photo.png", png_bytes, "image/png")}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 201
    assert _leftover_temp_files() == []


@pytest.mark.asyncio
async def test_upload_accepts_valid_json_content(client, auth_headers):
    files = {"file": ("data.json", b'{"ok": true}', "application/json")}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,content_type,content",
    [
        ("photo.jpg", "image/jpeg", b"\xff\xd8\xff" + b"rest-of-jpeg-is-irrelevant-here"),
        ("photo.gif", "image/gif", b"GIF87a" + b"rest-of-gif-is-irrelevant-here"),
        ("photo2.gif", "image/gif", b"GIF89a" + b"rest-of-gif-is-irrelevant-here"),
        ("photo.webp", "image/webp", b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"filler"),
        ("doc.pdf", "application/pdf", b"%PDF-1.4\n" + b"rest-of-pdf-is-irrelevant-here"),
        ("note.csv", "text/csv", b"a,b,c\n1,2,3"),
        ("note.md", "text/markdown", b"# heading\n\nbody text"),
    ],
)
async def test_upload_accepts_every_supported_signature(
    client, auth_headers, filename, content_type, content
):
    files = {"file": (filename, content, content_type)}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["content_type"] == content_type
    assert _leftover_temp_files() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,claimed_type,content",
    [
        ("fake.jpg", "image/jpeg", b"GIF87a-this-is-actually-a-gif"),
        ("fake.gif", "image/gif", b"%PDF-1.4-this-is-actually-a-pdf"),
        ("fake.webp", "image/webp", b"not-riff-at-all-just-text"),
        ("fake.pdf", "application/pdf", b"\x89PNG\r\n\x1a\n-this-is-actually-a-png"),
    ],
)
async def test_upload_rejects_mismatched_signature_for_every_binary_type(
    client, auth_headers, filename, claimed_type, content
):
    files = {"file": (filename, content, claimed_type)}
    resp = await client.post("/api/v1/files", files=files, headers=auth_headers)
    assert resp.status_code == 415
    assert _leftover_temp_files() == []


@pytest.mark.asyncio
async def test_delete_file(client, auth_headers):
    files = {"file": ("gone.txt", b"bye", "text/plain")}
    upload = await client.post("/api/v1/files", files=files, headers=auth_headers)
    file_id = upload.json()["id"]

    delete = await client.delete(f"/api/v1/files/{file_id}", headers=auth_headers)
    assert delete.status_code == 204

    get_after = await client.get(f"/api/v1/files/{file_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_file_not_visible_to_other_user(client, auth_headers):
    files = {"file": ("secret.txt", b"shh", "text/plain")}
    upload = await client.post("/api/v1/files", files=files, headers=auth_headers)
    file_id = upload.json()["id"]

    await client.post(
        "/api/v1/auth/register", json={"email": "other2@example.com", "password": "otherpass1"}
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "other2@example.com", "password": "otherpass1"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get(f"/api/v1/files/{file_id}", headers=other_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_file_content(client, auth_headers):
    original = b"the quick brown fox jumps over the lazy dog"
    files = {"file": ("fox.txt", original, "text/plain")}
    upload = await client.post("/api/v1/files", files=files, headers=auth_headers)
    file_id = upload.json()["id"]

    resp = await client.get(f"/api/v1/files/{file_id}/content", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content == original
    assert resp.headers["content-type"].startswith("text/plain")
    assert "fox.txt" in resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_download_file_content_not_visible_to_other_user(client, auth_headers):
    files = {"file": ("secret.txt", b"shh", "text/plain")}
    upload = await client.post("/api/v1/files", files=files, headers=auth_headers)
    file_id = upload.json()["id"]

    await client.post(
        "/api/v1/auth/register", json={"email": "other3@example.com", "password": "otherpass1"}
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "other3@example.com", "password": "otherpass1"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get(f"/api/v1/files/{file_id}/content", headers=other_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_file_content_requires_auth(client, auth_headers):
    files = {"file": ("note.txt", b"hi", "text/plain")}
    upload = await client.post("/api/v1/files", files=files, headers=auth_headers)
    file_id = upload.json()["id"]

    resp = await client.get(f"/api/v1/files/{file_id}/content")
    assert resp.status_code == 401
