import itertools
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator, model_validator

_TYPE_TABLE: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "string_list": list[str],
    "integer_list": list[int],
}
_STRUCTURED_TYPES = frozenset({"enum", "object"})
_ALL_TYPES = frozenset(_TYPE_TABLE) | _STRUCTURED_TYPES

# Schema-definition limits (not data limits - these bound how big/deep a caller's
# *schema* may be, independent of max_upload_size_bytes-style content limits
# elsewhere). All deliberately generous for real use, tight enough to make abuse
# (a pathologically deep/wide schema meant to blow up prompt size or build time)
# cheap to reject outright.
_MAX_NESTING_DEPTH = 4
_MAX_TOTAL_FIELDS = 50
_MAX_CHOICES = 50
_MAX_CHOICE_LENGTH = 100
_MAX_PATTERN_LENGTH = 200
_MAX_EXPLICIT_REPEAT = 100

# Heuristic ReDoS guard, not a formal proof of linear-time safety: catches the
# textbook catastrophic-backtracking shape (a quantified group that itself contains
# a quantifier, e.g. "(a+)+", "(a*)+") plus unreasonably large explicit repeat
# counts. It does not catch every pathological pattern (e.g. some overlapping-
# alternation cases like "(a|a)*"), so this is defense against the common/severe
# cases, paired with a hard length cap, not a sandboxed regex engine.
_NESTED_QUANTIFIER_RE = re.compile(r"\([^()]*[+*][^()]*\)[+*]")
_EXPLICIT_REPEAT_RE = re.compile(r"\{(\d+)(?:,(\d+)?)?\}")

_nested_model_counter = itertools.count()


class SchemaBuildError(Exception):
    """Raised when a validated SchemaDef cannot be turned into a model."""


def _validate_safe_pattern(pattern: str) -> None:
    if len(pattern) > _MAX_PATTERN_LENGTH:
        raise ValueError(f"'pattern' exceeds the maximum length of {_MAX_PATTERN_LENGTH}")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"'pattern' is not a valid regular expression: {exc}") from exc
    if _NESTED_QUANTIFIER_RE.search(pattern):
        raise ValueError(
            "'pattern' contains a quantified group nested inside another quantifier "
            "(e.g. '(a+)+'), which can cause catastrophic backtracking - rejected"
        )
    for match in _EXPLICIT_REPEAT_RE.finditer(pattern):
        for count in match.groups():
            if count and int(count) > _MAX_EXPLICIT_REPEAT:
                raise ValueError(
                    f"'pattern' has an explicit repeat count over {_MAX_EXPLICIT_REPEAT} - rejected"
                )


class FieldDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    description: str = ""
    required: bool = True

    # type == "enum"
    choices: list[str] | None = None
    # type == "object" (recursive - a nested object's own field list)
    fields: list["FieldDef"] | None = None
    # type in ("integer", "number")
    ge: float | None = None
    le: float | None = None
    # type == "string"
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None

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
        if value not in _ALL_TYPES:
            allowed = ", ".join(sorted(_ALL_TYPES))
            raise ValueError(f"unknown field type '{value}'; allowed types: {allowed}")
        return value

    @model_validator(mode="after")
    def validate_type_specific_constraints(self) -> "FieldDef":
        if self.type == "enum":
            if not self.choices:
                raise ValueError("an 'enum' field must define a non-empty 'choices' list")
            if len(self.choices) > _MAX_CHOICES:
                raise ValueError(f"'choices' exceeds the maximum of {_MAX_CHOICES} entries")
            if len(set(self.choices)) != len(self.choices):
                raise ValueError("'choices' entries must be unique")
            if any(len(c) > _MAX_CHOICE_LENGTH for c in self.choices):
                raise ValueError(f"each 'choices' entry must be at most {_MAX_CHOICE_LENGTH} chars")
        elif self.choices is not None:
            raise ValueError("'choices' is only valid for an 'enum' field")

        if self.type == "object":
            if not self.fields:
                raise ValueError("an 'object' field must define a non-empty 'fields' list")
        elif self.fields is not None:
            raise ValueError("'fields' is only valid for an 'object' field")

        if self.type in ("integer", "number"):
            if self.ge is not None and self.le is not None and self.ge > self.le:
                raise ValueError("'ge' must be less than or equal to 'le'")
        elif self.ge is not None or self.le is not None:
            raise ValueError("'ge'/'le' are only valid for 'integer'/'number' fields")

        if self.type == "string":
            if (
                self.min_length is not None
                and self.max_length is not None
                and self.min_length > self.max_length
            ):
                raise ValueError("'min_length' must be less than or equal to 'max_length'")
            if self.pattern is not None:
                _validate_safe_pattern(self.pattern)
        elif self.min_length is not None or self.max_length is not None or self.pattern is not None:
            raise ValueError(
                "'min_length'/'max_length'/'pattern' are only valid for 'string' fields"
            )

        return self


def _validate_field_tree(fields: list[FieldDef], *, depth: int) -> int:
    """Recursively validates uniqueness-within-level and depth, returning the total
    field count across this level and everything nested beneath it. Each nesting
    level gets its own name-uniqueness scope (a nested object's "name" field doesn't
    collide with a sibling top-level "name" field - they're different paths)."""
    if depth > _MAX_NESTING_DEPTH:
        raise ValueError(f"schema nesting exceeds the maximum depth of {_MAX_NESTING_DEPTH}")

    names = [f.name for f in fields]
    if len(names) != len(set(names)):
        raise ValueError("field names must be unique within the same level")

    total = len(fields)
    for field_def in fields:
        if field_def.type == "object":
            total += _validate_field_tree(field_def.fields or [], depth=depth + 1)
    return total


class SchemaDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[FieldDef]
    # Optional few-shot examples (each a dict of field_name -> value matching
    # `fields`), inlined into the system prompt (app/prompts/registry.py) to steer
    # the model's output format. There's no schema-storage feature in this codebase
    # to pull "stored" examples from - a schema is submitted fresh with every
    # request - so these ride along with the schema itself instead.
    examples: list[dict] | None = None

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[FieldDef]) -> list[FieldDef]:
        if not value:
            raise ValueError("schema must define at least one field")
        total = _validate_field_tree(value, depth=1)
        if total > _MAX_TOTAL_FIELDS:
            raise ValueError(
                f"schema defines {total} field(s) (including nested), exceeding the "
                f"maximum of {_MAX_TOTAL_FIELDS}"
            )
        return value


class SchemaValidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    json_schema: dict[str, Any]


def _field_annotation(field_def: FieldDef, *, model_name_prefix: str) -> tuple[Any, dict[str, Any]]:
    """Returns (python type annotation, extra Field() kwargs) for one field, not yet
    wrapped for required/optional - build_model handles that uniformly for every type."""
    if field_def.type == "enum":
        choices = tuple(field_def.choices or ())
        return Literal[choices], {}

    if field_def.type == "object":
        nested_name = (
            f"{model_name_prefix}_{field_def.name.capitalize()}{next(_nested_model_counter)}"
        )
        nested_model = _build_model_from_fields(field_def.fields or [], model_name=nested_name)
        return nested_model, {}

    python_type = _TYPE_TABLE[field_def.type]
    constraints: dict[str, Any] = {}
    if field_def.type in ("integer", "number"):
        if field_def.ge is not None:
            constraints["ge"] = field_def.ge
        if field_def.le is not None:
            constraints["le"] = field_def.le
    if field_def.type == "string":
        if field_def.min_length is not None:
            constraints["min_length"] = field_def.min_length
        if field_def.max_length is not None:
            constraints["max_length"] = field_def.max_length
        if field_def.pattern is not None:
            constraints["pattern"] = field_def.pattern
    return python_type, constraints


def _build_model_from_fields(fields: list[FieldDef], *, model_name: str) -> type[BaseModel]:
    field_definitions: dict[str, tuple[Any, Any]] = {}
    for field_def in fields:
        python_type, constraints = _field_annotation(field_def, model_name_prefix=model_name)
        annotation = python_type if field_def.required else python_type | None
        default = ... if field_def.required else None
        field_definitions[field_def.name] = (
            annotation,
            Field(default, description=field_def.description, **constraints),
        )

    # mypy can't resolve create_model's overloads against a **-unpacked dict, even
    # typed exactly as `dict[str, tuple[Any, Any]]` - a known pydantic/mypy stub
    # limitation, not a real type error (verified correct at runtime above).
    return create_model(  # type: ignore[call-overload]
        model_name,
        __config__=ConfigDict(extra="forbid"),
        **field_definitions,
    )


def build_model(schema: SchemaDef, *, model_name: str = "DynamicAnswer") -> type[BaseModel]:
    try:
        return _build_model_from_fields(schema.fields, model_name=model_name)
    except SchemaBuildError:
        raise
    except Exception as exc:
        raise SchemaBuildError(f"failed to build model: {exc}") from exc
