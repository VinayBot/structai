from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
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


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectResponse]:
    projects = await project_service.list_projects(session, user_id=user.id)
    return [ProjectResponse.model_validate(p, from_attributes=True) for p in projects]


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
