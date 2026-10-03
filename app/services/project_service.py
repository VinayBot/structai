from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.project import Project


async def create_project(session: AsyncSession, *, user_id: str, name: str) -> Project:
    project = Project(user_id=user_id, name=name)
    session.add(project)
    await session.commit()
    return project


async def list_projects(session: AsyncSession, *, user_id: str) -> list[Project]:
    result = await session.scalars(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    return list(result.all())


async def get_project(session: AsyncSession, *, user_id: str, project_id: str) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if project is None:
        raise NotFoundError("project not found")
    return project


async def delete_project(session: AsyncSession, *, user_id: str, project_id: str) -> None:
    project = await get_project(session, user_id=user_id, project_id=project_id)
    await session.delete(project)
    await session.commit()
