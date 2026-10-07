from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db import get_session
from app.models.user import User
from app.schemas.admin import AdminUsageRow, AdminUserResponse, UpdateRoleRequest
from app.schemas.pagination import Page
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=Page[AdminUserResponse])
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Page[AdminUserResponse]:
    users, total = await admin_service.list_users(session, limit=limit, offset=offset)
    return Page(
        items=[AdminUserResponse.model_validate(u, from_attributes=True) for u in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminUserResponse:
    user = await admin_service.set_user_role(
        session, admin=admin, target_user_id=user_id, role=body.role
    )
    return AdminUserResponse.model_validate(user, from_attributes=True)


@router.get("/usage", response_model=Page[AdminUsageRow])
async def list_usage(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Page[AdminUsageRow]:
    rows, total = await admin_service.list_usage_today(session, limit=limit, offset=offset)
    return Page(
        items=[
            AdminUsageRow(user_id=user_id, email=email, count_today=count)
            for user_id, email, count in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
