from fastapi import APIRouter, Depends, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse as FileStreamResponse

from app.config import Settings, get_settings
from app.core.deps import get_current_user
from app.core.errors import PayloadTooLargeError
from app.db import get_session
from app.models.user import User
from app.schemas.files import FileResponse
from app.schemas.pagination import Page
from app.services import file_service

router = APIRouter(prefix="/files", tags=["files"])


#  Content-Length on a multipart/form-data request is the size of the *whole*
# body - boundary markers, this part's own Content-Disposition/Content-Type headers,
# and any other form fields - not just the uploaded file's bytes. That overhead is
# typically well under a kilobyte per field, so this slack keeps it from causing a
# false 413 on a file that's legitimately right at the limit, while still fast-failing
# anything far over it before a byte of the body is read off the wire.
_CONTENT_LENGTH_SLACK_BYTES = 8 * 1024


def _reject_oversized_content_length(request: Request, max_size_bytes: int) -> None:
    """Fast-path only. This header is client-supplied and approximate (see slack
    comment above), so it's never trusted as the sole guard - save_file's own running
    byte counter during the actual read is the authoritative check."""
    declared = request.headers.get("content-length")
    if declared is None:
        return
    try:
        declared_bytes = int(declared)
    except ValueError:
        return
    if declared_bytes > max_size_bytes + _CONTENT_LENGTH_SLACK_BYTES:
        raise PayloadTooLargeError(f"file exceeds the {max_size_bytes}-byte upload limit")


@router.post("", response_model=FileResponse, status_code=201)
async def upload_file(
    request: Request,
    file: UploadFile,
    chat_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    _reject_oversized_content_length(request, settings.max_upload_size_bytes)
    attachment = await file_service.save_file(
        session,
        user_id=user.id,
        chat_id=chat_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        file=file,
        upload_dir=settings.upload_dir,
        max_size_bytes=settings.max_upload_size_bytes,
        allowed_content_types=settings.allowed_upload_content_type_set,
    )
    return FileResponse.model_validate(attachment, from_attributes=True)


@router.get("", response_model=Page[FileResponse])
async def list_files(
    chat_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[FileResponse]:
    files, total = await file_service.list_files(
        session, user_id=user.id, chat_id=chat_id, limit=limit, offset=offset
    )
    return Page(
        items=[FileResponse.model_validate(f, from_attributes=True) for f in files],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    attachment = await file_service.get_file(session, user_id=user.id, file_id=file_id)
    return FileResponse.model_validate(attachment, from_attributes=True)


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await file_service.delete_file(session, user_id=user.id, file_id=file_id)


@router.get("/{file_id}/content")
async def get_file_content(
    file_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileStreamResponse:
    # Ownership/authorization (get_file raises 404 for a missing-or-not-yours file) is
    # resolved before touching the filesystem at all. Starlette's FileResponse streams
    # the file off disk in chunks and handles Content-Disposition/Range itself - no
    # full-file read into memory here.
    attachment = await file_service.get_file(session, user_id=user.id, file_id=file_id)
    return FileStreamResponse(
        path=attachment.storage_path,
        media_type=attachment.content_type,
        filename=attachment.filename,
    )
