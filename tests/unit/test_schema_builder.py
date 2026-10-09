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


def test_primitive_type_json_schema_unaffected_by_the_new_types():
    """The six original types must produce exactly the same JSON Schema shape as
    before enum/object/constraints existed - no incidental regression."""
    schema = SchemaDef(fields=[FieldDef(name="title", type="string", description="d")])
    model = build_model(schema)
    props = model.model_json_schema()["properties"]
    assert props["title"] == {"title": "Title", "description": "d", "type": "string"}


# --- enum -------------------------------------------------------------------


def test_enum_accepts_a_listed_choice():
    schema = SchemaDef(fields=[FieldDef(name="color", type="enum", choices=["red", "green"])])
    model = build_model(schema)
    assert model(color="red").color == "red"


def test_enum_rejects_an_unlisted_choice():
    schema = SchemaDef(fields=[FieldDef(name="color", type="enum", choices=["red", "green"])])
    model = build_model(schema)
    with pytest.raises(ValidationError):
        model(color="purple")


def test_enum_json_schema_lists_the_choices():
    schema = SchemaDef(fields=[FieldDef(name="color", type="enum", choices=["red", "green"])])
    model = build_model(schema)
    assert model.model_json_schema()["properties"]["color"]["enum"] == ["red", "green"]


def test_enum_requires_non_empty_choices():
    with pytest.raises(ValidationError):
        FieldDef(name="color", type="enum", choices=[])
    with pytest.raises(ValidationError):
        FieldDef(name="color", type="enum")


def test_enum_rejects_duplicate_choices():
    with pytest.raises(ValidationError):
        FieldDef(name="color", type="enum", choices=["red", "red"])


def test_enum_rejects_too_many_choices():
    with pytest.raises(ValidationError):
        FieldDef(name="color", type="enum", choices=[f"c{i}" for i in range(51)])


def test_enum_rejects_an_overly_long_choice():
    with pytest.raises(ValidationError):
        FieldDef(name="color", type="enum", choices=["x" * 101])


def test_choices_rejected_on_a_non_enum_type():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", choices=["a", "b"])


# --- object (nesting) --------------------------------------------------------


def test_nested_object_accepts_a_matching_value():
    schema = SchemaDef(
        fields=[
            FieldDef(
                name="person",
                type="object",
                fields=[
                    FieldDef(name="name", type="string"),
                    FieldDef(name="age", type="integer"),
                ],
            )
        ]
    )
    model = build_model(schema)
    instance = model(person={"name": "Alice", "age": 30})
    assert instance.person.name == "Alice"
    assert instance.person.age == 30


def test_nested_object_rejects_a_mismatched_inner_field():
    schema = SchemaDef(
        fields=[
            FieldDef(name="person", type="object", fields=[FieldDef(name="age", type="integer")])
        ]
    )
    model = build_model(schema)
    with pytest.raises(ValidationError):
        model(person={"age": "not-a-number"})


def test_nested_object_json_schema_uses_a_ref_with_a_unique_name():
    schema = SchemaDef(
        fields=[
            FieldDef(name="a", type="object", fields=[FieldDef(name="x", type="string")]),
            FieldDef(name="b", type="object", fields=[FieldDef(name="x", type="string")]),
        ]
    )
    model = build_model(schema)
    json_schema = model.model_json_schema()
    # Two structurally-identical nested objects must still get distinct $defs
    # entries - generated model names are unique, not reused.
    assert len(json_schema["$defs"]) == 2
    ref_a = json_schema["properties"]["a"]["$ref"]
    ref_b = json_schema["properties"]["b"]["$ref"]
    assert ref_a != ref_b


def test_object_requires_non_empty_fields():
    with pytest.raises(ValidationError):
        FieldDef(name="person", type="object", fields=[])
    with pytest.raises(ValidationError):
        FieldDef(name="person", type="object")


def test_fields_rejected_on_a_non_object_type():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", fields=[FieldDef(name="y", type="string")])


def test_nested_object_field_names_scoped_per_level():
    """A nested object's field can share a name with a top-level (sibling) field -
    they're different paths, not a collision."""
    schema = SchemaDef(
        fields=[
            FieldDef(name="title", type="string"),
            FieldDef(
                name="inner",
                type="object",
                fields=[FieldDef(name="title", type="string")],
            ),
        ]
    )
    model = build_model(schema)
    instance = model(title="outer", inner={"title": "inner-value"})
    assert instance.title == "outer"
    assert instance.inner.title == "inner-value"


def test_duplicate_names_within_the_same_nested_level_rejected():
    with pytest.raises(ValidationError):
        SchemaDef(
            fields=[
                FieldDef(
                    name="person",
                    type="object",
                    fields=[
                        FieldDef(name="x", type="string"),
                        FieldDef(name="x", type="integer"),
                    ],
                )
            ]
        )


# --- nesting depth / total field count --------------------------------------


def _nested_depth(n: int) -> list[FieldDef]:
    if n == 1:
        return [FieldDef(name="leaf", type="string")]
    return [FieldDef(name="nested", type="object", fields=_nested_depth(n - 1))]


def test_nesting_at_the_max_depth_is_accepted():
    SchemaDef(fields=_nested_depth(4))


def test_nesting_beyond_the_max_depth_is_rejected():
    with pytest.raises(ValidationError):
        SchemaDef(fields=_nested_depth(5))


def test_total_field_count_at_the_max_is_accepted():
    SchemaDef(fields=[FieldDef(name=f"f{i}", type="string") for i in range(50)])


def test_total_field_count_over_the_max_is_rejected():
    with pytest.raises(ValidationError):
        SchemaDef(fields=[FieldDef(name=f"f{i}", type="string") for i in range(51)])


def test_total_field_count_includes_nested_fields():
    """48 top-level fields + a nested object with 3 more = 51 total, over the cap -
    even though no single level looks oversized on its own."""
    top_level = [FieldDef(name=f"f{i}", type="string") for i in range(48)]
    nested = FieldDef(
        name="extra",
        type="object",
        fields=[FieldDef(name=f"n{i}", type="string") for i in range(3)],
    )
    with pytest.raises(ValidationError):
        SchemaDef(fields=[*top_level, nested])


# --- numeric / string constraints --------------------------------------------


def test_ge_le_boundaries_are_inclusive():
    schema = SchemaDef(fields=[FieldDef(name="score", type="integer", ge=0, le=100)])
    model = build_model(schema)
    assert model(score=0).score == 0
    assert model(score=100).score == 100
    with pytest.raises(ValidationError):
        model(score=-1)
    with pytest.raises(ValidationError):
        model(score=101)


def test_ge_greater_than_le_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="integer", ge=10, le=5)


def test_ge_le_rejected_on_a_non_numeric_type():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", ge=1)


def test_min_max_length_boundaries_are_inclusive():
    schema = SchemaDef(fields=[FieldDef(name="code", type="string", min_length=2, max_length=4)])
    model = build_model(schema)
    assert model(code="ab").code == "ab"
    assert model(code="abcd").code == "abcd"
    with pytest.raises(ValidationError):
        model(code="a")
    with pytest.raises(ValidationError):
        model(code="abcde")


def test_min_length_greater_than_max_length_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", min_length=10, max_length=5)


def test_pattern_match_and_mismatch():
    schema = SchemaDef(fields=[FieldDef(name="code", type="string", pattern=r"^[A-Z]{3}-\d{4}$")])
    model = build_model(schema)
    assert model(code="ABC-1234").code == "ABC-1234"
    with pytest.raises(ValidationError):
        model(code="not-matching")


def test_pattern_json_schema_includes_the_pattern():
    schema = SchemaDef(fields=[FieldDef(name="code", type="string", pattern=r"^[A-Z]+$")])
    model = build_model(schema)
    assert model.model_json_schema()["properties"]["code"]["pattern"] == r"^[A-Z]+$"


def test_pattern_too_long_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", pattern="a" * 201)


def test_pattern_with_invalid_syntax_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", pattern="(unterminated")


def test_pattern_with_catastrophic_nested_quantifier_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", pattern="(a+)+")
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", pattern="(a*)*b")


def test_pattern_with_oversized_explicit_repeat_rejected():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="string", pattern="a{1,99999}")


def test_pattern_rejected_on_a_non_string_type():
    with pytest.raises(ValidationError):
        FieldDef(name="x", type="integer", pattern="[0-9]+")
