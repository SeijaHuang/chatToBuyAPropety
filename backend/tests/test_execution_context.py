"""Tests for agent.shared.execution_context — ExecutionContext dataclass."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from agent.shared.execution_context import ExecutionContext
from models.shared.enums import EUserIntent
from models.shared.submodels import CollectedData


class TestExecutionContext:
    """ExecutionContext frozen dataclass tests."""

    def test_frozen_dataclass_prevents_mutation(self) -> None:
        """Assigning any field on a frozen dataclass raises FrozenInstanceError."""
        ctx: ExecutionContext = ExecutionContext(
            session_id="sess-1",
            intent=EUserIntent.RECOMMEND_SUBURBS,
            user_needs=CollectedData(),
        )
        with pytest.raises(FrozenInstanceError):
            ctx.session_id = "new-id"  # type: ignore[misc]

    def test_default_values_are_none(self) -> None:
        """Optional fields default to None when not provided."""
        ctx: ExecutionContext = ExecutionContext(
            session_id="sess-1",
            intent=EUserIntent.OPEN_ENDED_QUERY,
            user_needs=CollectedData(),
        )
        assert ctx.property_lat is None
        assert ctx.property_lng is None
        assert ctx.property_address is None
        assert ctx.target_entity_id is None
        assert ctx.target_entity_type is None
        assert ctx.target_entity_label is None

    def test_triggered_at_auto_filled(self) -> None:
        """triggered_at is automatically set via default_factory on construction."""
        ctx1: ExecutionContext = ExecutionContext(
            session_id="sess-1",
            intent=EUserIntent.LIST_PROPERTIES,
            user_needs=CollectedData(),
        )
        ctx2: ExecutionContext = ExecutionContext(
            session_id="sess-2",
            intent=EUserIntent.LIST_PROPERTIES,
            user_needs=CollectedData(),
        )
        assert isinstance(ctx1.triggered_at, datetime)
        assert isinstance(ctx2.triggered_at, datetime)
        # Two separate constructions should produce different timestamps
        assert ctx1.triggered_at != ctx2.triggered_at

    def test_user_needs_accepts_collected_data(self) -> None:
        """user_needs accepts a CollectedData instance (not UserNeeds)."""
        data: CollectedData = CollectedData()
        ctx: ExecutionContext = ExecutionContext(
            session_id="sess-1",
            intent=EUserIntent.RECOMMEND_SUBURBS,
            user_needs=data,
        )
        assert ctx.user_needs is data
        assert isinstance(ctx.user_needs, CollectedData)

    def test_all_fields_constructable_and_readable(self) -> None:
        """Every field can be set at construction and read back correctly."""
        user_needs: CollectedData = CollectedData()
        triggered: datetime = datetime.now(tz=UTC)
        ctx: ExecutionContext = ExecutionContext(
            session_id="sess-abc",
            intent=EUserIntent.PROPERTY_DETAIL,
            user_needs=user_needs,
            target_entity_id="prop_123",
            target_entity_type="property",
            target_entity_label="123 Swan St, Richmond",
            property_lat=-37.82,
            property_lng=144.96,
            property_address="123 Swan St, Richmond VIC 3121",
            triggered_at=triggered,
        )
        assert ctx.session_id == "sess-abc"
        assert ctx.intent == EUserIntent.PROPERTY_DETAIL
        assert ctx.user_needs is user_needs
        assert ctx.target_entity_id == "prop_123"
        assert ctx.target_entity_type == "property"
        assert ctx.target_entity_label == "123 Swan St, Richmond"
        assert ctx.property_lat == -37.82
        assert ctx.property_lng == 144.96
        assert ctx.property_address == "123 Swan St, Richmond VIC 3121"
        assert ctx.triggered_at == triggered
