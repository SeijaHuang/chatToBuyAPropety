"""Tests for agent.orchestration.context_resolver — ContextResolver."""

from datetime import UTC, datetime

import pytest

from agent.orchestration.context_resolver import ContextResolver
from agent.shared.context import ExecutionContext
from models.shared.enums import EIntendedUse, EPropertyType, EUserIntent
from models.shared.routing import EExecutionMode, ETriggerSource, RoutingPayload
from models.shared.submodels import CollectedData, M1PropertyNeeds, M3SuburbPreference
from models.shared.user_needs import UserNeeds

# ============================================================================
# Test doubles
# ============================================================================


async def _geocode_success_async(address: str) -> tuple[float, float, str]:
    """Stub geocode function that always returns fixed coordinates."""
    return (-37.8136, 144.9631, "Melbourne VIC 3000")


async def _geocode_none_async(address: str) -> tuple[float, float, str] | None:
    """Stub geocode function that returns None (address not found)."""
    return None


async def _geocode_raises_async(address: str) -> tuple[float, float, str] | None:
    """Stub geocode function that always raises."""
    raise ConnectionError("Geocoding API unavailable")


# ============================================================================
# Helpers
# ============================================================================


def _make_routing(
    session_id: str = "test-session",
    intent: EUserIntent = EUserIntent.RECOMMEND_SUBURBS,
    collect: CollectedData | None = None,
) -> RoutingPayload:
    """Build a minimal RoutingPayload for testing."""
    user_needs: UserNeeds = UserNeeds(
        session_id=session_id,
        generated_at=datetime.now(tz=UTC),
        collected=collect if collect is not None else CollectedData(),
        initial_intent=intent,
    )
    return RoutingPayload(
        intent=intent,
        session_id=session_id,
        user_needs=user_needs,
        execution_mode=EExecutionMode.CODE_DRIVEN,
        agents_hint=[],
        triggered_at=datetime.now(tz=UTC),
        trigger_source=ETriggerSource.AUTO_COMPLETE,
    )


# ============================================================================
# Tests
# ============================================================================


class TestContextResolver:
    """ContextResolver tests — field mapping and geocode enrichment."""

    @pytest.mark.anyio
    async def test_fields_copied_from_routing_payload(self) -> None:
        """Session ID and intent are copied directly from RoutingPayload."""
        resolver: ContextResolver = ContextResolver()
        routing: RoutingPayload = _make_routing(
            session_id="abc-123",
            intent=EUserIntent.LIST_PROPERTIES,
        )

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.session_id == "abc-123"
        assert context.intent == EUserIntent.LIST_PROPERTIES

    @pytest.mark.anyio
    async def test_user_needs_is_collected_data_not_user_needs(self) -> None:
        """user_needs field = routing.user_needs.collected (PRD I1)."""
        m1: M1PropertyNeeds = M1PropertyNeeds(
            property_type=EPropertyType.HOUSE,
            min_bedrooms=3,
            intended_use=EIntendedUse.OWNER_OCCUPIER,
        )
        collected: CollectedData = CollectedData(m1=m1)
        resolver: ContextResolver = ContextResolver()
        routing: RoutingPayload = _make_routing(collect=collected)

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.user_needs is collected
        assert context.user_needs.m1.property_type == EPropertyType.HOUSE
        assert context.user_needs.m1.min_bedrooms == 3

    @pytest.mark.anyio
    async def test_target_entity_fields_are_none(self) -> None:
        """target_entity_id/type/label default to None."""
        resolver: ContextResolver = ContextResolver()
        routing: RoutingPayload = _make_routing()

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.target_entity_id is None
        assert context.target_entity_type is None
        assert context.target_entity_label is None

    @pytest.mark.anyio
    async def test_coordinates_none_when_no_geocode(self) -> None:
        """When geocode_async is None, coordinates stay None."""
        resolver: ContextResolver = ContextResolver(geocode_async=None)
        routing: RoutingPayload = _make_routing()

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.property_lat is None
        assert context.property_lng is None
        assert context.property_address is None

    @pytest.mark.anyio
    async def test_geocode_success_sets_coordinates(self) -> None:
        """Successful geocode sets property_lat/lng/address."""
        collected: CollectedData = CollectedData(
            m3=M3SuburbPreference(commute_destination="Melbourne")
        )
        resolver: ContextResolver = ContextResolver(geocode_async=_geocode_success_async)
        routing: RoutingPayload = _make_routing(collect=collected)

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.property_lat == -37.8136
        assert context.property_lng == 144.9631
        assert context.property_address == "Melbourne VIC 3000"

    @pytest.mark.anyio
    async def test_geocode_returns_none_coordinates_stay_none(self) -> None:
        """When geocode returns None, coordinates stay None."""
        collected: CollectedData = CollectedData(
            m3=M3SuburbPreference(commute_destination="Unknown Place")
        )
        resolver: ContextResolver = ContextResolver(geocode_async=_geocode_none_async)
        routing: RoutingPayload = _make_routing(collect=collected)

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.property_lat is None
        assert context.property_lng is None
        assert context.property_address is None

    @pytest.mark.anyio
    async def test_geocode_exception_coordinates_stay_none(self) -> None:
        """When geocode raises, coordinates stay None (no exception propagated)."""
        collected: CollectedData = CollectedData(
            m3=M3SuburbPreference(commute_destination="Melbourne")
        )
        resolver: ContextResolver = ContextResolver(geocode_async=_geocode_raises_async)
        routing: RoutingPayload = _make_routing(collect=collected)

        # Should NOT raise — exception is caught and logged
        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.property_lat is None
        assert context.property_lng is None
        assert context.property_address is None

    @pytest.mark.anyio
    async def test_pick_address_prefers_target_entity_label(self) -> None:
        """_pick_address returns target_entity_label when present."""
        collected: CollectedData = CollectedData(
            m3=M3SuburbPreference(commute_destination="Commute Address")
        )
        # Set target_entity_label via setattr since it's not on the model yet
        routing: RoutingPayload = _make_routing(collect=collected)
        object.__setattr__(routing, "target_entity_label", "Target Address")
        resolve_call_count: list[str] = []

        async def capture_geocode(address: str) -> tuple[float, float, str] | None:
            resolve_call_count.append(address)
            return (-37.0, 145.0, address)

        resolver: ContextResolver = ContextResolver(geocode_async=capture_geocode)

        await resolver.resolve_async(routing)

        assert len(resolve_call_count) == 1
        assert resolve_call_count[0] == "Target Address"

    @pytest.mark.anyio
    async def test_pick_address_falls_back_to_commute_destination(self) -> None:
        """_pick_address uses commute_destination when no target_entity_label."""
        collected: CollectedData = CollectedData(
            m3=M3SuburbPreference(commute_destination="Commute Address")
        )
        resolver: ContextResolver = ContextResolver(geocode_async=_geocode_success_async)
        routing: RoutingPayload = _make_routing(collect=collected)

        context: ExecutionContext = await resolver.resolve_async(routing)

        # Geocode was called with commute_destination, so coordinates are set
        assert context.property_lat == -37.8136
        assert context.property_lng == 144.9631

    @pytest.mark.anyio
    async def test_no_address_skips_geocode(self) -> None:
        """When no address is available, geocode is not called."""
        resolver: ContextResolver = ContextResolver(geocode_async=_geocode_success_async)
        routing: RoutingPayload = _make_routing()

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.property_lat is None
        assert context.property_lng is None

    @pytest.mark.anyio
    async def test_triggered_at_is_set(self) -> None:
        """ExecutionContext.triggered_at is auto-populated."""
        resolver: ContextResolver = ContextResolver()
        routing: RoutingPayload = _make_routing()

        context: ExecutionContext = await resolver.resolve_async(routing)

        assert context.triggered_at is not None
        assert isinstance(context.triggered_at, datetime)
