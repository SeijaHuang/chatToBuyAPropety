"""PTV DTOs that cross the HTTP boundary via Agent PTV Endpoints.

These inherit PropertyAIBaseModel for automatic camelCase alias generation
(stop_id -> stopId, route_type -> routeType, etc.).

Internal dataclasses (EPTVRouteType, PTVNearbyStop, etc.) live in
agent/tools/ptv/ptv_models.py and are NOT re-exported here.
"""

from models.base import PropertyAIBaseModel


class PTVNearbyStopDTO(PropertyAIBaseModel):
    """Nearby stop serialised for API response / TransportComposer.

    Note:
        walking distance and walking time are NOT included here.
        They are computed by GoogleRoutesTool and merged into
        TransportAssessment by TransportComposer.
    """

    stop_id: str
    stop_name: str
    route_type: str
    distance_metres: int
    suburb: str | None
    routes_serving: list[str]
    has_accessible_access: bool | None
    peak_frequency_minutes: int | None
    has_disruption: bool
    disruption_title: str | None


class PTVNearbyStopResult(PropertyAIBaseModel):
    """PTVNearbyStopsTool output — public transport coverage around a property.

    Serialised into ToolResult.data. Used as the response_model for
    POST /agent/ptv/nearby-stops.
    """

    property_lat: float
    property_lng: float
    nearby_stops: list[PTVNearbyStopDTO]

    # Counts by route type
    train_stops_nearby: int
    tram_stops_nearby: int
    bus_stops_nearby: int

    # Nearest stop summaries
    nearest_train_stop: PTVNearbyStopDTO | None
    nearest_train_distance_metres: int | None
    nearest_tram_stop: PTVNearbyStopDTO | None
    nearest_tram_distance_metres: int | None

    # Route summaries
    train_lines: list[str]
    tram_routes: list[str]
    night_network_available: bool

    # Frequency summaries
    peak_frequency_summary: str | None
    offpeak_frequency_summary: str | None

    # Query metadata
    search_radius_metres: int
    generated_at_utc: str
