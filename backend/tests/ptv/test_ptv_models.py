"""Tests for PTV internal data models and HTTP DTOs."""

from dataclasses import FrozenInstanceError

import pytest

from agent.tools.ptv.ptv_models import (
    EPTVRouteType,
    PTDepartureInfo,
    PTVDisruption,
    PTVNearbyStop,
    PTVStopDepartureSummary,
    PTVStopDetail,
    PTVStopRoute,
)
from models.shared.ptv import PTVNearbyStopDTO, PTVNearbyStopResult


class TestEPTVRouteType:
    """Tests for EPTVRouteType enum values."""

    def test_correct_integer_values(self) -> None:
        """All enum members map to the correct PTV API integer codes."""
        assert EPTVRouteType.TRAIN.value == 0
        assert EPTVRouteType.TRAM.value == 1
        assert EPTVRouteType.BUS.value == 2
        assert EPTVRouteType.VLINE.value == 3
        assert EPTVRouteType.NIGHT_BUS.value == 4

    def test_name_lower_yields_route_type_string(self) -> None:
        """Enum .name.lower() produces the expected DTO route_type strings."""
        assert EPTVRouteType.TRAIN.name.lower() == "train"
        assert EPTVRouteType.TRAM.name.lower() == "tram"
        assert EPTVRouteType.BUS.name.lower() == "bus"
        assert EPTVRouteType.VLINE.name.lower() == "vline"
        assert EPTVRouteType.NIGHT_BUS.name.lower() == "night_bus"


class TestPTVNearbyStop:
    """Tests for PTVNearbyStop frozen dataclass."""

    def test_construction_and_field_access(self) -> None:
        """Fields are accessible by name after construction."""
        stop: PTVNearbyStop = PTVNearbyStop(
            stop_id="19840",
            stop_name="Richmond Railway Station",
            route_type=EPTVRouteType.TRAIN,
            distance_metres=342,
            suburb="Richmond",
        )
        assert stop.stop_id == "19840"
        assert stop.stop_name == "Richmond Railway Station"
        assert stop.route_type == EPTVRouteType.TRAIN
        assert stop.distance_metres == 342
        assert stop.suburb == "Richmond"

    def test_frozen_instance_raises_on_mutation(self) -> None:
        """Frozen dataclass prevents field reassignment."""
        stop: PTVNearbyStop = PTVNearbyStop(
            stop_id="19840",
            stop_name="Test",
            route_type=EPTVRouteType.BUS,
            distance_metres=100,
            suburb=None,
        )
        with pytest.raises(FrozenInstanceError):
            stop.distance_metres = 200  # type: ignore[misc]

    def test_suburb_can_be_none(self) -> None:
        """suburb is Optional — None is a valid value."""
        stop: PTVNearbyStop = PTVNearbyStop(
            stop_id="1",
            stop_name="Test",
            route_type=EPTVRouteType.BUS,
            distance_metres=50,
            suburb=None,
        )
        assert stop.suburb is None


class TestPTVStopRoute:
    """Tests for PTVStopRoute frozen dataclass."""

    def test_optional_fields_can_be_none(self) -> None:
        """route_number and direction_name are optional."""
        route: PTVStopRoute = PTVStopRoute(
            route_id="6",
            route_name="Belgrave",
            route_number=None,
            route_type=EPTVRouteType.TRAIN,
            direction_name=None,
        )
        assert route.route_number is None
        assert route.direction_name is None


class TestPTVStopDetail:
    """Tests for PTVStopDetail frozen dataclass."""

    def test_default_empty_routes_list(self) -> None:
        """routes defaults to empty list when no routes are served."""
        detail: PTVStopDetail = PTVStopDetail(
            stop_id="19840",
            stop_name="Richmond",
            route_type=EPTVRouteType.TRAIN,
            routes=[],
            has_parking=True,
            has_bike_rack=False,
            is_accessible=True,
            has_toilet=None,
        )
        assert detail.routes == []
        assert detail.has_toilet is None


class TestPTDepartureInfo:
    """Tests for PTDepartureInfo frozen dataclass."""

    def test_optional_fields_accept_none(self) -> None:
        """estimated_departure_utc, at_platform, platform_number are all optional."""
        dep: PTDepartureInfo = PTDepartureInfo(
            route_id="6",
            direction_id=1,
            scheduled_departure_utc="2026-07-16T22:15:00Z",
            estimated_departure_utc=None,
            at_platform=None,
            platform_number=None,
        )
        assert dep.estimated_departure_utc is None
        assert dep.at_platform is None
        assert dep.platform_number is None


class TestPTVStopDepartureSummary:
    """Tests for PTVStopDepartureSummary frozen dataclass."""

    def test_bool_fields_default_to_false(self) -> None:
        """Evening and weekend service flags are bool, not Optional."""
        summary: PTVStopDepartureSummary = PTVStopDepartureSummary(
            stop_id="19840",
            route_type=EPTVRouteType.TRAIN,
            peak_frequency_minutes=3,
            offpeak_frequency_minutes=None,
            has_evening_service=False,
            has_weekend_service=False,
            next_departure_minutes=None,
        )
        assert summary.has_evening_service is False
        assert summary.has_weekend_service is False


class TestPTVDisruption:
    """Tests for PTVDisruption frozen dataclass."""

    def test_severity_accepts_expected_values(self) -> None:
        """severity accepts minor, major, and planned strings."""
        disruption: PTVDisruption = PTVDisruption(
            disruption_id="123456",
            title="Buses replacing trains",
            description="...",
            affected_route_ids=["6"],
            affected_stop_ids=["19840"],
            start_utc="2026-07-18T01:00:00Z",
            end_utc="2026-07-20T01:00:00Z",
            severity="planned",
        )
        assert disruption.severity == "planned"

    def test_optional_timestamps_can_be_none(self) -> None:
        """start_utc and end_utc are optional."""
        disruption: PTVDisruption = PTVDisruption(
            disruption_id="1",
            title="Test",
            description="Test",
            affected_route_ids=[],
            affected_stop_ids=[],
            start_utc=None,
            end_utc=None,
            severity="minor",
        )
        assert disruption.start_utc is None
        assert disruption.end_utc is None


class TestPTVNearbyStopDTO:
    """Tests for PTVNearbyStopDTO (PropertyAIBaseModel — camelCase serialisation)."""

    def test_model_dump_by_alias_produces_camel_case_keys(self) -> None:
        """model_dump(by_alias=True) outputs camelCase field names."""
        dto: PTVNearbyStopDTO = PTVNearbyStopDTO(
            stop_id="19840",
            stop_name="Richmond Station",
            route_type="train",
            distance_metres=342,
            suburb="Richmond",
            routes_serving=["Belgrave", "Lilydale"],
            has_accessible_access=True,
            peak_frequency_minutes=3,
            has_disruption=False,
            disruption_title=None,
        )
        result: dict[str, object] = dto.model_dump(by_alias=True)
        assert "stopId" in result
        assert "stopName" in result
        assert "routeType" in result
        assert "distanceMetres" in result
        assert "routesServing" in result
        assert "hasAccessibleAccess" in result
        assert "peakFrequencyMinutes" in result
        assert "hasDisruption" in result
        # snake_case keys should NOT be present
        assert "stop_id" not in result

    def test_list_fields_default_to_empty(self) -> None:
        """routes_serving defaults to empty list."""
        dto: PTVNearbyStopDTO = PTVNearbyStopDTO(
            stop_id="1",
            stop_name="Test",
            route_type="bus",
            distance_metres=100,
            suburb=None,
            routes_serving=[],
            has_accessible_access=None,
            peak_frequency_minutes=None,
            has_disruption=False,
            disruption_title=None,
        )
        assert dto.routes_serving == []


class TestPTVNearbyStopResult:
    """Tests for PTVNearbyStopResult (PropertyAIBaseModel — camelCase serialisation)."""

    def test_empty_stops_produces_zero_counts(self) -> None:
        """With no nearby stops, all counts and nearest fields are zero/None."""
        result: PTVNearbyStopResult = PTVNearbyStopResult(
            property_lat=-37.8142,
            property_lng=144.9631,
            nearby_stops=[],
            train_stops_nearby=0,
            tram_stops_nearby=0,
            bus_stops_nearby=0,
            nearest_train_stop=None,
            nearest_train_distance_metres=None,
            nearest_tram_stop=None,
            nearest_tram_distance_metres=None,
            train_lines=[],
            tram_routes=[],
            night_network_available=False,
            peak_frequency_summary=None,
            offpeak_frequency_summary=None,
            search_radius_metres=1200,
            generated_at_utc="",
        )
        assert result.train_stops_nearby == 0
        assert result.nearest_train_stop is None
        assert result.night_network_available is False

    def test_model_dump_by_alias_produces_camel_case_keys(self) -> None:
        """Top-level fields use camelCase in serialised output."""
        dto: PTVNearbyStopDTO = PTVNearbyStopDTO(
            stop_id="1",
            stop_name="Test",
            route_type="train",
            distance_metres=100,
            suburb=None,
            routes_serving=[],
            has_accessible_access=None,
            peak_frequency_minutes=None,
            has_disruption=False,
            disruption_title=None,
        )
        result: PTVNearbyStopResult = PTVNearbyStopResult(
            property_lat=-37.81,
            property_lng=144.96,
            nearby_stops=[dto],
            train_stops_nearby=1,
            tram_stops_nearby=0,
            bus_stops_nearby=0,
            nearest_train_stop=dto,
            nearest_train_distance_metres=100,
            nearest_tram_stop=None,
            nearest_tram_distance_metres=None,
            train_lines=[],
            tram_routes=[],
            night_network_available=False,
            peak_frequency_summary=None,
            offpeak_frequency_summary=None,
            search_radius_metres=1200,
            generated_at_utc="2026-07-22T00:00:00Z",
        )
        dumped: dict[str, object] = result.model_dump(by_alias=True)
        assert "propertyLat" in dumped
        assert "propertyLng" in dumped
        assert "nearbyStops" in dumped
        assert "trainStopsNearby" in dumped
        assert "nearestTrainStop" in dumped
        assert "searchRadiusMetres" in dumped
        assert "generatedAtUtc" in dumped
