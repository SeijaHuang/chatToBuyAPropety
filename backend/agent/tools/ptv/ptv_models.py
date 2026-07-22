"""PTV API v3 internal data models.

All dataclasses are frozen (immutable). DTOs that cross the HTTP boundary
(PTVNearbyStopDTO, PTVNearbyStopResult) live in models/shared/ptv.py
so they are co-located with the rest of the API contract layer.
"""

from dataclasses import dataclass
from enum import IntEnum


class EPTVRouteType(IntEnum):
    """PTV API v3 route_type values.

    IntEnum rather than StrEnum because the PTV API natively uses integer
    route_type codes (0=Train, 1=Tram, 2=Bus, 3=VLine, 4=NightBus).
    String representations are derived via .name.lower() when constructing
    serialised DTOs in models/shared/ptv.py.
    """

    TRAIN = 0
    TRAM = 1
    BUS = 2
    VLINE = 3
    NIGHT_BUS = 4


@dataclass(frozen=True)
class PTVNearbyStop:
    """A single PTV stop near a property, with distance and metadata.

    Note:
        walking_duration and walking_distance are NOT owned by PTV.
        They are computed by GoogleRoutesTool and merged later by
        TransportComposer.
    """

    stop_id: str
    stop_name: str
    route_type: EPTVRouteType
    distance_metres: int
    suburb: str | None


@dataclass(frozen=True)
class PTVStopRoute:
    """A route that stops at a given PTV stop."""

    route_id: str
    route_name: str
    route_number: str | None
    route_type: EPTVRouteType
    direction_name: str | None


@dataclass(frozen=True)
class PTVStopDetail:
    """Full stop detail including facilities and served routes."""

    stop_id: str
    stop_name: str
    route_type: EPTVRouteType
    routes: list[PTVStopRoute]
    has_parking: bool
    has_bike_rack: bool
    is_accessible: bool
    has_toilet: bool | None


@dataclass(frozen=True)
class PTDepartureInfo:
    """Scheduled or estimated departure from a stop."""

    route_id: str
    direction_id: int
    scheduled_departure_utc: str
    estimated_departure_utc: str | None
    at_platform: bool | None
    platform_number: str | None


@dataclass(frozen=True)
class PTVStopDepartureSummary:
    """Aggregated departure frequency for a stop in a time window."""

    stop_id: str
    route_type: EPTVRouteType
    peak_frequency_minutes: int | None
    offpeak_frequency_minutes: int | None
    has_evening_service: bool
    has_weekend_service: bool
    next_departure_minutes: int | None


@dataclass(frozen=True)
class PTVDisruption:
    """A service disruption affecting a route or stop."""

    disruption_id: str
    title: str
    description: str
    affected_route_ids: list[str]
    affected_stop_ids: list[str]
    start_utc: str | None
    end_utc: str | None
    severity: str
