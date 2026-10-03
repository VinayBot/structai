from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

_TYPE_TABLE: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "string_list": list[str],
    "integer_list": list[int],
}


class SchemaBuildError(Exception):
    """Raised when a validated SchemaDef cannot be turned into a model."""


class FieldDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    description: str = ""
    required: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.isidentifier():
            raise ValueError(f"'{value}' is not a valid field name")
        if value.startswith("_") or value.startswith("model_"):
            raise ValueError(f"field name '{value}' may not start with '_' or 'model_'")
        return value

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in _TYPE_TABLE:
            allowed = ", ".join(sorted(_TYPE_TABLE))
            raise ValueError(f"unknown field type '{value}'; allowed types: {allowed}")
        return value


class SchemaDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[FieldDef]

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[FieldDef]) -> list[FieldDef]:
        if not value:
            raise ValueError("schema must define at least one field")
        names = [f.name for f in value]
        if len(names) != len(set(names)):
            raise ValueError("field names must be unique")
        return value


class SchemaValidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    json_schema: dict[str, Any]


def build_model(schema: SchemaDef, *, model_name: str = "DynamicAnswer") -> type[BaseModel]:
    try:
        field_definitions: dict[str, tuple] = {}
        for field_def in schema.fields:
            python_type = _TYPE_TABLE[field_def.type]
            annotation = python_type if field_def.required else python_type | None
            default = ... if field_def.required else None
            field_definitions[field_def.name] = (
                annotation,
                Field(default, description=field_def.description),
            )

        return create_model(
            model_name,
            __config__=ConfigDict(extra="forbid"),
            **field_definitions,
        )
    except SchemaBuildError:
        raise
    except Exception as exc:
        raise SchemaBuildError(f"failed to build model: {exc}") from exc
