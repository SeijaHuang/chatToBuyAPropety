"""Tests for tools/extraction_schema.py — Story S-A."""

import json
from typing import Any, cast

from tools.extraction_schema import EXTRACT_REQUIREMENTS_TOOL

_M1_TO_M4_FIELDS = [
    "property_type",
    "min_bedrooms",
    "max_bedrooms",
    "min_bathrooms",
    "min_carspaces",
    "min_land_size",
    "max_land_size",
    "wants_pool",
    "wants_outdoor",
    "wants_study",
    "intended_use",
    "household_size",
    "has_children",
    "needs_school_zone",
    "has_pets",
    "work_from_home",
    "target_tenant",
    "commute_destination",
    "commute_max_mins",
    "commute_mode",
    "preferred_suburbs",
    "excluded_suburbs",
    "lifestyle_vibe",
    "budget_min",
    "budget_max",
    "deposit_amount",
    "pre_tax_salary",
    "is_joint",
    "partner_salary",
    "first_home_buyer",
]


def _function() -> dict[str, Any]:
    return cast(dict[str, Any], EXTRACT_REQUIREMENTS_TOOL["function"])


def _parameters() -> dict[str, Any]:
    return cast(dict[str, Any], _function()["parameters"])


def _properties() -> dict[str, Any]:
    return cast(dict[str, Any], _parameters()["properties"])


def test_schema_is_json_serialisable() -> None:
    """SA-1: Schema can be serialised by json.dumps() without error."""
    json.dumps(EXTRACT_REQUIREMENTS_TOOL)


def test_tool_name_is_extract_requirements() -> None:
    """SA-2: name field value is strictly equal to 'extract_requirements'."""
    assert _function()["name"] == "extract_requirements"


def test_required_list_is_empty() -> None:
    """SA-3: The required list is empty — all fields are optional."""
    required: list[str] = _parameters()["required"]
    assert required == []


def test_control_fields_absent_from_schema() -> None:
    """SA-4: Control fields module_complete, next_question, and user_intent are not in properties."""
    properties = _properties()
    assert "module_complete" not in properties
    assert "next_question" not in properties
    assert "user_intent" not in properties


def test_all_business_fields_are_defined_in_properties() -> None:
    """All M1–M4 business fields must exist as keys in the properties object."""
    properties = _properties()
    for field in _M1_TO_M4_FIELDS:
        assert field in properties, f"Business field '{field}' is missing from properties"


def test_property_type_enum_values() -> None:
    """SA-5: property_type enum values match the specification exactly."""
    assert _properties()["property_type"]["enum"] == [
        "house",
        "townhouse",
        "unit",
        "apartment",
        "villa",
        "any",
    ]


def test_commute_mode_enum_values() -> None:
    """SA-6: commute_mode enum values match the specification exactly."""
    assert _properties()["commute_mode"]["enum"] == [
        "train",
        "car",
        "tram",
        "bus",
        "any",
    ]


def test_list_fields_have_correct_array_type() -> None:
    """SA-7: preferred_suburbs and excluded_suburbs are arrays of strings."""
    for field in ("preferred_suburbs", "excluded_suburbs"):
        prop = _properties()[field]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "string"}
