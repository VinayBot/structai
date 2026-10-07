from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.projects import ProjectCreateRequest, ProjectResponse
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await project_service.create_project(session, user_id=user.id, name=body.name)
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.get("", response_model=Page[ProjectResponse])
async def list_projects(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[ProjectResponse]:
    projects, total = await project_service.list_projects(
        session, user_id=user.id, limit=limit, offset=offset
    )
    return Page(
        items=[ProjectResponse.model_validate(p, from_attributes=True) for p in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await project_service.get_project(session, user_id=user.id, project_id=project_id)
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await project_service.delete_project(session, user_id=user.id, project_id=project_id)
