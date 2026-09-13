"""Coordinate, endpoint and location-resolution tests."""

from __future__ import annotations

import math

import pytest

from custom_components.openrouteservice_travel_time.const import (
    ENDPOINT_ENTITY,
    ENDPOINT_FIXED,
)
from custom_components.openrouteservice_travel_time.location import (
    EndpointUnavailableError,
    resolve_endpoint,
)
from custom_components.openrouteservice_travel_time.models import (
    Coordinates,
    endpoint_from_config,
    endpoint_signature,
    entity_endpoint_config,
    fixed_endpoint_config,
    coordinates_from_config,
)


def test_coordinates_use_openrouteservice_order() -> None:
    """ORS requests use longitude/latitude rather than Home Assistant order."""
    point = Coordinates(latitude=55.167, longitude=-1.691)

    assert point.ors_pair == [-1.691, 55.167]


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (math.nan, 0.0),
        (91.0, 0.0),
        (-91.0, 0.0),
        (0.0, math.inf),
        (0.0, 181.0),
        (0.0, -181.0),
    ],
)
def test_coordinates_reject_invalid_ranges(latitude: float, longitude: float) -> None:
    """Invalid coordinate values are rejected before a provider call."""
    with pytest.raises(ValueError):
        Coordinates(latitude=latitude, longitude=longitude)


def test_coordinates_from_location_selector() -> None:
    """HA location-selector values convert to typed coordinates."""
    point = coordinates_from_config({"latitude": 55.1, "longitude": -1.6})

    assert point == Coordinates(55.1, -1.6)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "55.1,-1.6",
        {"longitude": -1.6},
        {"latitude": 55.1},
        {"latitude": True, "longitude": -1.6},
        {"latitude": "55.1", "longitude": -1.6},
        {"latitude": 55.1, "longitude": False},
        {"latitude": 55.1, "longitude": "-1.6"},
    ],
)
def test_coordinates_from_config_rejects_malformed_values(value: object) -> None:
    """Malformed location data never becomes an implicit/fallback route."""
    with pytest.raises(ValueError):
        coordinates_from_config(value)


def test_fixed_endpoint_is_canonical_and_alpha1_compatible() -> None:
    """Fixed endpoint data is explicit while alpha.1 data remains readable."""
    canonical = fixed_endpoint_config({"latitude": 55.1, "longitude": -1.6})

    assert canonical["type"] == ENDPOINT_FIXED
    parsed = endpoint_from_config(canonical)
    legacy = endpoint_from_config({"latitude": 55.1, "longitude": -1.6})

    assert parsed.coordinates == Coordinates(55.1, -1.6)
    assert legacy.coordinates == parsed.coordinates
    assert endpoint_signature(canonical) == "fixed:55.100000,-1.600000"


def test_dynamic_endpoint_identity_uses_entity_not_current_coordinates() -> None:
    """A moving route keeps a stable duplicate-detection identity."""
    config = entity_endpoint_config("person.iain")

    parsed = endpoint_from_config(config)

    assert parsed.kind == ENDPOINT_ENTITY
    assert parsed.entity_id == "person.iain"
    assert endpoint_signature(config) == "entity:person.iain"


@pytest.mark.parametrize(
    "entity_id",
    ["sensor.latitude", "person", "device_tracker.", ".iain"],
)
def test_dynamic_endpoint_rejects_unsupported_entity_ids(entity_id: str) -> None:
    """Only person/device_tracker entities are valid dynamic endpoints."""
    with pytest.raises(ValueError):
        entity_endpoint_config(entity_id)


def test_endpoint_rejects_invalid_persisted_shape() -> None:
    """Unknown endpoint types do not silently become fixed locations."""
    with pytest.raises(ValueError):
        endpoint_from_config({"type": "mystery"})


async def test_resolve_dynamic_person_coordinates(hass) -> None:
    """Person coordinates are resolved from current HA state every update."""
    hass.states.async_set(
        "person.iain",
        "not_home",
        {"latitude": 55.2, "longitude": -1.7},
    )

    point = resolve_endpoint(hass, entity_endpoint_config("person.iain"))

    assert point == Coordinates(55.2, -1.7)


async def test_resolve_dynamic_device_tracker_coordinates(hass) -> None:
    """Device trackers are supported as dynamic endpoints."""
    hass.states.async_set(
        "device_tracker.phone",
        "home",
        {"latitude": 55.3, "longitude": -1.8},
    )

    point = resolve_endpoint(
        hass,
        entity_endpoint_config("device_tracker.phone"),
    )

    assert point == Coordinates(55.3, -1.8)


async def test_resolve_fixed_endpoint_does_not_read_home_location(hass) -> None:
    """Fixed routes return exactly the configured point."""
    point = resolve_endpoint(
        hass,
        fixed_endpoint_config({"latitude": 54.9, "longitude": -1.4}),
    )

    assert point == Coordinates(54.9, -1.4)


@pytest.mark.parametrize("state", ["unknown", "unavailable"])
async def test_dynamic_entity_unknown_or_unavailable(hass, state: str) -> None:
    """Untrusted entity states make the route unavailable."""
    hass.states.async_set(
        "person.iain",
        state,
        {"latitude": 55.2, "longitude": -1.7},
    )

    with pytest.raises(EndpointUnavailableError):
        resolve_endpoint(hass, entity_endpoint_config("person.iain"))


async def test_dynamic_entity_missing(hass) -> None:
    """A deleted entity does not fall back to Home Assistant home."""
    with pytest.raises(EndpointUnavailableError):
        resolve_endpoint(hass, entity_endpoint_config("person.iain"))


async def test_dynamic_entity_without_coordinates(hass) -> None:
    """A location entity without coordinates is not guessed."""
    hass.states.async_set("person.iain", "not_home", {})

    with pytest.raises(EndpointUnavailableError):
        resolve_endpoint(hass, entity_endpoint_config("person.iain"))
