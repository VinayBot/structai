from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.files import FileResponse
from app.schemas.pagination import Page
from app.services import file_service

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=FileResponse, status_code=201)
async def upload_file(
    file: UploadFile,
    chat_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    content = await file.read()
    attachment = await file_service.save_file(
        session,
        user_id=user.id,
        chat_id=chat_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        content=content,
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
) -> Response:
    content, content_type, _filename = await file_service.read_content(
        session, user_id=user.id, file_id=file_id
    )
    return Response(content=content, media_type=content_type)
