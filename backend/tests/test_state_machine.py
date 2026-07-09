"""Tests for conversation/state_machine.py — Story S-B."""

from conversation.state_machine import (
    get_current_module,
    is_module_complete,
    merge_extracted_fields,
)
from models.shared.conversation_state import ConversationStateDTO
from models.shared.enums import EIntendedUse, EModule, EPropertyType
from models.shared.submodels import CollectedData, CompletionStatus


def test_m1_complete_when_all_required_fields_present() -> None:
    data = CollectedData()
    data.m1.property_type = EPropertyType.HOUSE
    data.m1.min_bedrooms = 3
    data.m1.intended_use = EIntendedUse.OWNER_OCCUPIER
    assert is_module_complete(EModule.M1_PROPERTY_NEEDS, data) is True


def test_m1_incomplete_when_property_type_missing() -> None:
    data = CollectedData()
    data.m1.min_bedrooms = 3
    data.m1.intended_use = EIntendedUse.OWNER_OCCUPIER
    assert is_module_complete(EModule.M1_PROPERTY_NEEDS, data) is False


def test_m1_incomplete_when_min_bedrooms_missing() -> None:
    data = CollectedData()
    data.m1.property_type = EPropertyType.HOUSE
    data.m1.intended_use = EIntendedUse.OWNER_OCCUPIER
    assert is_module_complete(EModule.M1_PROPERTY_NEEDS, data) is False


def test_m1_incomplete_when_intended_use_missing() -> None:
    data = CollectedData()
    data.m1.property_type = EPropertyType.HOUSE
    data.m1.min_bedrooms = 3
    assert is_module_complete(EModule.M1_PROPERTY_NEEDS, data) is False


def test_m2_requires_target_tenant_when_investment() -> None:
    data = CollectedData()
    data.m1.intended_use = EIntendedUse.INVESTMENT
    data.m2.household_size = 1
    data.m2.has_children = False
    assert is_module_complete(EModule.M2_LIFESTYLE, data) is False


def test_m2_does_not_require_target_tenant_when_owner_occupier() -> None:
    data = CollectedData()
    data.m1.intended_use = EIntendedUse.OWNER_OCCUPIER
    data.m2.household_size = 2
    data.m2.has_children = False
    assert is_module_complete(EModule.M2_LIFESTYLE, data) is True


def test_m3_complete_when_destination_and_mins_present() -> None:
    data = CollectedData()
    data.m3.commute_destination = "CBD"
    data.m3.commute_max_mins = 30
    assert is_module_complete(EModule.M3_SUBURB_PREFERENCE, data) is True


def test_m4_complete_when_budget_max_present() -> None:
    data = CollectedData()
    data.m4.budget_max = 800000
    assert is_module_complete(EModule.M4_BUDGET, data) is True


def test_current_module_returns_m1_when_m1_incomplete() -> None:
    completion = CompletionStatus()
    assert get_current_module(completion) == EModule.M1_PROPERTY_NEEDS


def test_current_module_returns_m2_when_m1_complete_m2_incomplete() -> None:
    completion = CompletionStatus(M1=True)
    assert get_current_module(completion) == EModule.M2_LIFESTYLE


def test_current_module_returns_complete_when_all_done() -> None:
    completion = CompletionStatus(M1=True, M2=True, M3=True, M4=True)
    assert get_current_module(completion) == EModule.COMPLETE


def test_nonlinear_jump_writes_to_correct_submodel() -> None:
    state = ConversationStateDTO(session_id="test-session-001")
    assert state.current_module == EModule.M1_PROPERTY_NEEDS
    merge_extracted_fields(state, {"commute_destination": "Melbourne CBD"})
    assert state.collected_data.m3.commute_destination == "Melbourne CBD"


def test_completion_status_recalculated_after_merge() -> None:
    state = ConversationStateDTO(session_id="test-session-001")
    merge_extracted_fields(
        state,
        {"property_type": "house", "min_bedrooms": 3, "intended_use": "owner_occupier"},
    )
    assert state.completion_status.M1 is True


def test_none_value_does_not_overwrite_existing_value() -> None:
    state = ConversationStateDTO(session_id="test-session-001")
    state.collected_data.m1.property_type = EPropertyType.HOUSE
    merge_extracted_fields(state, {"property_type": None})
    assert state.collected_data.m1.property_type == "house"
