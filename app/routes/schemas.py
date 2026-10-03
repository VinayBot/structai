from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models.user import User
from app.schemas.builder import SchemaBuildError, SchemaDef, SchemaValidateResponse, build_model

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.post("/validate")
async def validate_schema(
    body: SchemaDef, _user: User = Depends(get_current_user)
) -> SchemaValidateResponse:
    try:
        model = build_model(body)
    except SchemaBuildError as exc:
        raise AppError(
            code="invalid_schema",
            message=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    return SchemaValidateResponse(valid=True, json_schema=model.model_json_schema())
