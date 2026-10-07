import json
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.models.file import FileAttachment

# The client-supplied Content-Type header is trivially spoofable - a request can
# claim "image/png" for an uploaded shell script just as easily as a real PNG.
# These checks verify the bytes actually look like what's claimed, closing that
# gap for the types in ALLOWED_UPLOAD_CONTENT_TYPES. Binary types get a real
# signature ("magic bytes") check; the text-ish types have no such signature, so
# they get the next best thing - a decode/parse check that at least rejects
# arbitrary binary data wearing a text content-type.
_MAGIC_BYTE_CHECKS: dict[str, Callable[[bytes], bool]] = {
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/gif": lambda b: b.startswith((b"GIF87a", b"GIF89a")),
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    "application/pdf": lambda b: b.startswith(b"%PDF-"),
}


def _content_matches_claimed_type(content: bytes, content_type: str) -> bool:
    check = _MAGIC_BYTE_CHECKS.get(content_type)
    if check is not None:
        return check(content)

    if content_type == "application/json":
        try:
            json.loads(content)
        except ValueError:
            return False
        return True

    if content_type in ("text/plain", "text/csv", "text/markdown"):
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True

    # Only reachable if allowed_upload_content_types grows a type with no entry
    # here - fail closed on an unverifiable type rather than silently accept it.
    return False


async def save_file(
    session: AsyncSession,
    *,
    user_id: str,
    chat_id: str | None,
    filename: str,
    content_type: str,
    content: bytes,
    upload_dir: str,
    max_size_bytes: int,
    allowed_content_types: set[str],
) -> FileAttachment:
    if content_type not in allowed_content_types:
        raise UnsupportedMediaTypeError(f"content type '{content_type}' is not accepted")

    if not _content_matches_claimed_type(content, content_type):
        raise UnsupportedMediaTypeError(
            f"file content does not match the claimed content type '{content_type}'"
        )

    if len(content) > max_size_bytes:
        raise PayloadTooLargeError(f"file exceeds the {max_size_bytes}-byte upload limit")

    user_dir = Path(upload_dir) / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex
    safe_name = Path(filename).name
    storage_path = user_dir / f"{file_id}_{safe_name}"
    storage_path.write_bytes(content)

    attachment = FileAttachment(
        id=file_id,
        user_id=user_id,
        chat_id=chat_id,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(content),
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


async def read_content(
    session: AsyncSession, *, user_id: str, file_id: str
) -> tuple[bytes, str, str]:
    attachment = await get_file(session, user_id=user_id, file_id=file_id)
    content = Path(attachment.storage_path).read_bytes()
    return content, attachment.content_type, attachment.filename
