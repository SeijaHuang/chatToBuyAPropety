"""Build ExecutionContext from RoutingPayload + optional geocode enrichment (PRD §S4.5)."""

from collections.abc import Awaitable, Callable
from typing import Protocol

import structlog

from agent.shared.context import ExecutionContext
from models.shared.routing import RoutingPayload
from models.shared.submodels import M3SuburbPreference

logger = structlog.get_logger()

# Prototype: geocode callable signature
GeocodeFunc = Callable[[str], Awaitable[tuple[float, float, str] | None]]
"""Async function: address → (lat, lng, formatted_address) | None."""


class IContextResolver(Protocol):
    """Protocol for context resolution strategies.

    Converts a RoutingPayload (Part 1 output) into an ExecutionContext
    suitable for Part 2 execution. Implementations may enrich the context
    with geocoding or other data sources.
    """

    async def resolve_async(self, routing: RoutingPayload) -> ExecutionContext:
        """Convert a RoutingPayload into an ExecutionContext."""
        ...


class ContextResolver(IContextResolver):
    """Build ExecutionContext from RoutingPayload + optional geocode enrichment.

    Design (PRD D3): geocode once here; PTV, GoogleRoutes, GooglePlaces
    all reuse the coordinates from ExecutionContext.
    """

    def __init__(self, geocode_async: GeocodeFunc | None = None) -> None:
        """Initialise with an optional geocode callable.

        Args:
            geocode_async: Optional async function that resolves an address
                           string to (lat, lng, formatted_address).  Pass None
                           in the prototype phase to skip geocoding.
        """
        self._geocode_async: GeocodeFunc | None = geocode_async

    async def resolve_async(self, routing: RoutingPayload) -> ExecutionContext:
        """Convert a RoutingPayload into an ExecutionContext.

        Steps:
          1. Copy session_id, intent, target_entity_* directly.
          2. Extract user_needs.collected (PRD decision I1).
          3. If geocode_async is available and an address is present,
             resolve coordinates; on failure, coordinates stay None.
        """
        context: ExecutionContext = ExecutionContext(
            session_id=routing.session_id,
            intent=routing.intent,
            user_needs=routing.user_needs.collected,
            target_entity_id=None,
            target_entity_type=None,
            target_entity_label=None,
        )

        # Attempt geocode enrichment when available
        if self._geocode_async is not None:
            address: str | None = self._pick_address(routing)
            if address:
                try:
                    coords: tuple[float, float, str] | None = await self._geocode_async(address)
                    if coords is not None:
                        lat: float = coords[0]
                        lng: float = coords[1]
                        formatted: str = coords[2]
                        # frozen dataclass — must use object.__setattr__
                        object.__setattr__(context, "property_lat", lat)
                        object.__setattr__(context, "property_lng", lng)
                        object.__setattr__(context, "property_address", formatted)
                except Exception:
                    log: structlog.BoundLogger = logger.bind(
                        session_id=routing.session_id, address=address
                    )
                    log.warning("geocode_failed_coordinates_remain_none")

        return context

    def _pick_address(self, routing: RoutingPayload) -> str | None:
        """Extract the best available address string for geocoding."""
        # Prefer target_entity_label when set
        target_label: str | None = getattr(routing, "target_entity_label", None)
        if target_label:
            return target_label
        # Fallback: use commute_destination from collected data
        m3: M3SuburbPreference = routing.user_needs.collected.m3
        if m3.commute_destination:
            return m3.commute_destination
        return None


def get_context_resolver() -> IContextResolver:
    """FastAPI dependency — returns a ContextResolver with no geocode enrichment."""
    return ContextResolver()
