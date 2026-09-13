"""Coordinate and route model tests."""

from __future__ import annotations

import math

import pytest

from custom_components.openrouteservice_travel_time.models import (
    Coordinates,
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
