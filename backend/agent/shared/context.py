"""Layer 0 — Immutable shared context passed to every Tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from models.shared.enums import EUserIntent
from models.shared.submodels import CollectedData


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context built by Orchestrator, passed to every Tool.

    - Generic fields copied directly from RoutingPayload
    - Coordinates/address resolved by ContextResolver (geocode once, shared by all Tools)
    - Tools extract only the fields they need via build_params()
    """

    # ── From RoutingPayload ──
    session_id: str
    intent: EUserIntent
    user_needs: CollectedData
    target_entity_id: str | None = None
    target_entity_type: str | None = None
    target_entity_label: str | None = None

    # ── Resolved by ContextResolver ──
    property_lat: float | None = None
    property_lng: float | None = None
    property_address: str | None = None

    # ── Execution metadata ──
    triggered_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
