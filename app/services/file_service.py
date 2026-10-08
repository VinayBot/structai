import asyncio
import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.models.file import FileAttachment

# Read/write in bounded chunks so neither a huge upload nor a slow client ever
# requires buffering the whole file in memory.
_CHUNK_SIZE_BYTES = 64 * 1024
# Longest signature we check (WEBP, byte 11) needs 12 bytes; 512 leaves generous
# headroom without reading meaningfully more of the file than necessary.
_SIGNATURE_PREFIX_BYTES = 512

# The client-supplied Content-Type header is trivially spoofable - a request can
# claim "image/png" for an uploaded shell script just as easily as a real PNG.
# These checks verify the bytes actually look like what's claimed, closing that
# gap for the types in ALLOWED_UPLOAD_CONTENT_TYPES. Binary types get a real
# signature ("magic bytes") check against just the first bytes of the stream;
# the text-ish types have no such signature, so they get the next best thing -
# a decode/parse check against the full (already size-capped) content on disk.
_MAGIC_BYTE_CHECKS: dict[str, Callable[[bytes], bool]] = {
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/gif": lambda b: b.startswith((b"GIF87a", b"GIF89a")),
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    "application/pdf": lambda b: b.startswith(b"%PDF-"),
}


def _is_valid_json(content: bytes) -> bool:
    try:
        json.loads(content)
    except ValueError:
        return False
    return True


def _is_valid_utf8(content: bytes) -> bool:
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


_FULL_CONTENT_CHECKS: dict[str, Callable[[bytes], bool]] = {
    "application/json": _is_valid_json,
    "text/plain": _is_valid_utf8,
    "text/csv": _is_valid_utf8,
    "text/markdown": _is_valid_utf8,
}


async def _write_chunked(
    file: UploadFile, tmp_path: Path, max_size_bytes: int
) -> tuple[int, bytes]:
    """Streams `file` into `tmp_path` in bounded chunks, off the event loop.

    Returns (total bytes written, first _SIGNATURE_PREFIX_BYTES of content). Raises
    PayloadTooLargeError the instant the running count exceeds max_size_bytes, without
    reading (or holding) any more of the stream than that.
    """
    total = 0
    prefix = b""
    handle = await asyncio.to_thread(tmp_path.open, "wb")
    try:
        while True:
            chunk = await file.read(_CHUNK_SIZE_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size_bytes:
                raise PayloadTooLargeError(f"file exceeds the {max_size_bytes}-byte upload limit")
            if len(prefix) < _SIGNATURE_PREFIX_BYTES:
                prefix += chunk[: _SIGNATURE_PREFIX_BYTES - len(prefix)]
            await asyncio.to_thread(handle.write, chunk)
    finally:
        await asyncio.to_thread(handle.close)
    return total, prefix


def _verify_content(tmp_path: Path, prefix: bytes, content_type: str) -> None:
    """Fail-closed: a content_type outside both check tables (i.e. someone widened
    ALLOWED_UPLOAD_CONTENT_TYPES without adding a matching entry here) is rejected
    rather than silently accepted unverified."""
    if content_type in _MAGIC_BYTE_CHECKS:
        matched = _MAGIC_BYTE_CHECKS[content_type](prefix)
    elif content_type in _FULL_CONTENT_CHECKS:
        full_content = tmp_path.read_bytes()
        matched = _FULL_CONTENT_CHECKS[content_type](full_content)
    else:
        matched = False

    if not matched:
        raise UnsupportedMediaTypeError(
            f"file content does not match the claimed content type '{content_type}'"
        )


async def save_file(
    session: AsyncSession,
    *,
    user_id: str,
    chat_id: str | None,
    filename: str,
    content_type: str,
    file: UploadFile,
    upload_dir: str,
    max_size_bytes: int,
    allowed_content_types: set[str],
) -> FileAttachment:
    if content_type not in allowed_content_types:
        raise UnsupportedMediaTypeError(f"content type '{content_type}' is not accepted")

    user_dir = Path(upload_dir) / user_id
    await asyncio.to_thread(user_dir.mkdir, parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex
    safe_name = Path(filename).name
    tmp_path = user_dir / f".tmp-{file_id}"

    try:
        total_bytes, prefix = await _write_chunked(file, tmp_path, max_size_bytes)
        await asyncio.to_thread(_verify_content, tmp_path, prefix, content_type)

        storage_path = user_dir / f"{file_id}_{safe_name}"
        await asyncio.to_thread(os.replace, tmp_path, storage_path)
    except BaseException:
        # BaseException, not Exception: a client disconnect surfaces as
        # asyncio.CancelledError, which is deliberately not an Exception subclass -
        # the temp file must still be cleaned up on that path too.
        await asyncio.to_thread(tmp_path.unlink, missing_ok=True)
        raise

    attachment = FileAttachment(
        id=file_id,
        user_id=user_id,
        chat_id=chat_id,
        filename=safe_name,
        content_type=content_type,
        size_bytes=total_bytes,
        storage_path=str(storage_path),
    )
    session.add(attachment)
    await session.commit()
    return attachment


async def list_files(
    session: AsyncSession,
    *,
    user_id: str,
    chat_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[FileAttachment], int]:
    filters = [FileAttachment.user_id == user_id]
    if chat_id is not None:
        filters.append(FileAttachment.chat_id == chat_id)

    total = await session.scalar(select(func.count()).select_from(FileAttachment).where(*filters))
    result = await session.scalars(
        select(FileAttachment)
        .where(*filters)
        .order_by(FileAttachment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.all()), total or 0


async def get_file(session: AsyncSession, *, user_id: str, file_id: str) -> FileAttachment:
    attachment = await session.scalar(
        select(FileAttachment).where(
            FileAttachment.id == file_id, FileAttachment.user_id == user_id
        )
    )
    if attachment is None:
        raise NotFoundError("file not found")
    return attachment


async def delete_file(session: AsyncSession, *, user_id: str, file_id: str) -> None:
    attachment = await get_file(session, user_id=user_id, file_id=file_id)
    Path(attachment.storage_path).unlink(missing_ok=True)
    await session.delete(attachment)
    await session.commit()
