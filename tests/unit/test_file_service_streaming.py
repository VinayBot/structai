"""Streaming-specific behavior of file_service.save_file that's awkward to exercise
through the HTTP layer: bounded memory use on a huge rejected upload, and that the
.tmp-* staging file never survives any failure path. Call save_file directly rather
than through tests/integration/test_files.py's client fixture, so the test process's
own memory profile reflects only what the service does with the stream."""

import asyncio
import tracemalloc

import pytest

from app.core.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from app.services import file_service


class _SyntheticUpload:
    """Stands in for fastapi.UploadFile, generating `total_size` bytes on demand
    without ever materializing them all at once - *as long as the caller asks for
    bounded chunks*. Deliberately mirrors real UploadFile.read() semantics for an
    unbounded call (size<0 or omitted means "give me everything remaining"), so
    if save_file ever regresses to a plain `await file.read()` with no size, this
    fake hands back the full `total_size` in one allocation and the memory
    assertion below actually catches it, instead of quietly capping it anyway."""

    def __init__(self, total_size: int):
        self._remaining = total_size

    async def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        n = self._remaining if size is None or size < 0 else min(size, self._remaining)
        self._remaining -= n
        return b"x" * n


@pytest.mark.asyncio
async def test_oversized_stream_rejected_without_buffering_it_in_memory(tmp_path):
    upload_dir = tmp_path / "uploads"
    stream_size = 200 * 1024 * 1024  # 200MB claimed - never materialized at once
    stream = _SyntheticUpload(total_size=stream_size)

    tracemalloc.start()
    try:
        with pytest.raises(PayloadTooLargeError):
            await file_service.save_file(
                session=None,  # failure path never touches the session
                user_id="u-huge",
                chat_id=None,
                filename="huge.txt",
                content_type="text/plain",
                file=stream,
                upload_dir=str(upload_dir),
                max_size_bytes=1024 * 1024,  # 1MB - far smaller than the stream
                allowed_content_types={"text/plain"},
            )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    # The stream claims 200MB; if save_file buffered it whole, peak would be on
    # that order. Bounded chunked reads/writes should keep it to a few chunks.
    assert peak < 5 * 1024 * 1024, f"peak traced memory was {peak} bytes - looks fully buffered"
    assert list(upload_dir.rglob(".tmp-*")) == []


@pytest.mark.asyncio
async def test_temp_file_removed_when_signature_check_fails(tmp_path):
    upload_dir = tmp_path / "uploads"
    stream = _SyntheticUpload(total_size=16)  # tiny, but doesn't start with a PNG signature

    with pytest.raises(UnsupportedMediaTypeError):
        await file_service.save_file(
            session=None,
            user_id="u-badsig",
            chat_id=None,
            filename="fake.png",
            content_type="image/png",
            file=stream,
            upload_dir=str(upload_dir),
            max_size_bytes=1024,
            allowed_content_types={"image/png"},
        )

    # The per-user directory itself is created up front and legitimately persists;
    # only the staged .tmp-* file must not survive a rejected upload.
    assert list(upload_dir.rglob(".tmp-*")) == []


@pytest.mark.asyncio
async def test_temp_file_removed_on_unexpected_write_failure(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    stream = _SyntheticUpload(total_size=16)

    def _boom(*_args, **_kwargs):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(file_service.os, "replace", _boom)

    with pytest.raises(OSError):
        await file_service.save_file(
            session=None,
            user_id="u-ioerror",
            chat_id=None,
            filename="note.txt",
            content_type="text/plain",
            file=stream,
            upload_dir=str(upload_dir),
            max_size_bytes=1024,
            allowed_content_types={"text/plain"},
        )

    assert list(upload_dir.rglob(".tmp-*")) == []


@pytest.mark.asyncio
async def test_unverifiable_content_type_fails_closed(tmp_path):
    """A content_type that's allow-listed but has no entry in either check table (e.g.
    someone widens ALLOWED_UPLOAD_CONTENT_TYPES without adding a matching verifier)
    must be rejected, not silently accepted unverified."""
    upload_dir = tmp_path / "uploads"
    stream = _SyntheticUpload(total_size=16)

    with pytest.raises(UnsupportedMediaTypeError):
        await file_service.save_file(
            session=None,
            user_id="u-unverifiable",
            chat_id=None,
            filename="mystery.bin",
            content_type="application/x-mystery",
            file=stream,
            upload_dir=str(upload_dir),
            max_size_bytes=1024,
            allowed_content_types={"application/x-mystery"},
        )

    assert list(upload_dir.rglob(".tmp-*")) == []


@pytest.mark.asyncio
async def test_temp_file_removed_on_client_disconnect(tmp_path):
    upload_dir = tmp_path / "uploads"

    class _DisconnectingUpload:
        async def read(self, size: int = -1) -> bytes:
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await file_service.save_file(
            session=None,
            user_id="u-disconnect",
            chat_id=None,
            filename="note.txt",
            content_type="text/plain",
            file=_DisconnectingUpload(),
            upload_dir=str(upload_dir),
            max_size_bytes=1024,
            allowed_content_types={"text/plain"},
        )

    assert list(upload_dir.rglob(".tmp-*")) == []
