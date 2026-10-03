import pytest
from pydantic import ValidationError

from app.schemas.builder import FieldDef, SchemaDef, SchemaValidateResponse, build_model


def test_build_model_valid_schema():
    schema = SchemaDef(
        fields=[
            FieldDef(name="title", type="string"),
            FieldDef(name="score", type="integer", required=False),
        ]
    )
    model = build_model(schema)

    instance = model(title="hello")
    assert instance.title == "hello"
    assert instance.score is None

    with pytest.raises(ValidationError):
        model(title="hello", extra_field="not allowed")


def test_duplicate_field_names_rejected():
    with pytest.raises(ValidationError):
        SchemaDef(
            fields=[
                FieldDef(name="x", type="string"),
                FieldDef(name="x", type="integer"),
            ]
        )


def test_unknown_type_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="unknown_type")


def test_reserved_prefix_names_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="_private", type="string")

    with pytest.raises(ValidationError):
        FieldDef(name="model_config", type="string")


def test_empty_fields_rejected():
    with pytest.raises(ValidationError):
        SchemaDef(fields=[])


def test_schema_validate_response_forbids_extra_fields():
    SchemaValidateResponse(valid=True, json_schema={"type": "object"})
    with pytest.raises(ValidationError):
        SchemaValidateResponse(valid=True, json_schema={}, extra_field="nope")


def test_all_supported_types_build():
    schema = SchemaDef(
        fields=[
            FieldDef(name="a", type="string"),
            FieldDef(name="b", type="integer"),
            FieldDef(name="c", type="number"),
            FieldDef(name="d", type="boolean"),
            FieldDef(name="e", type="string_list"),
            FieldDef(name="f", type="integer_list"),
        ]
    )
    model = build_model(schema)
    instance = model(a="x", b=1, c=1.5, d=True, e=["x"], f=[1, 2])
    assert instance.f == [1, 2]
