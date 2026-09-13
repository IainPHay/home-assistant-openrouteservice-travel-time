"""Tests for dynamic endpoint location resolution."""

import pytest

from custom_components.openrouteservice_travel_time.location import (
    EndpointUnavailableError,
    resolve_endpoint,
)
from custom_components.openrouteservice_travel_time.models import entity_endpoint_config


PERSON = entity_endpoint_config("person.abbi")
TRACKER = entity_endpoint_config("device_tracker.abbi_phone")


def test_person_uses_direct_coordinates_first(hass) -> None:
    """A person with coordinates is resolved directly."""
    hass.states.async_set(
        "person.abbi",
        "not_home",
        {"latitude": 55.1701, "longitude": -1.6812, "source": "device_tracker.abbi_phone"},
    )
    hass.states.async_set(
        "device_tracker.abbi_phone",
        "not_home",
        {"latitude": 54.0, "longitude": -2.0},
    )

    result = resolve_endpoint(hass, PERSON)

    assert result.latitude == pytest.approx(55.1701)
    assert result.longitude == pytest.approx(-1.6812)


def test_person_in_home_zone_uses_zone_coordinates(hass) -> None:
    """A zoned person without coordinates uses the explicit containing zone."""
    hass.states.async_set(
        "zone.home",
        "0",
        {"latitude": 55.167, "longitude": -1.691, "friendly_name": "Home"},
    )
    hass.states.async_set(
        "person.abbi",
        "home",
        {"in_zones": ["zone.home"], "source": "device_tracker.abbi_phone"},
    )
    hass.states.async_set(
        "device_tracker.abbi_phone",
        "home",
        {"latitude": 54.0, "longitude": -2.0},
    )

    result = resolve_endpoint(hass, PERSON)

    assert result.latitude == pytest.approx(55.167)
    assert result.longitude == pytest.approx(-1.691)


def test_person_zone_matches_friendly_name(hass) -> None:
    """A named person state can match an explicitly reported zone friendly name."""
    hass.states.async_set(
        "zone.abbi_school",
        "0",
        {"latitude": 55.2, "longitude": -1.7, "friendly_name": "Abbi School"},
    )
    hass.states.async_set(
        "zone.other",
        "0",
        {"latitude": 55.3, "longitude": -1.8, "friendly_name": "Other"},
    )
    hass.states.async_set(
        "person.abbi",
        "Abbi School",
        {
            "in_zones": ["zone.other", "zone.abbi_school"],
            "source": "device_tracker.abbi_phone",
        },
    )

    result = resolve_endpoint(hass, PERSON)

    assert result.latitude == pytest.approx(55.2)
    assert result.longitude == pytest.approx(-1.7)


def test_person_falls_back_to_source_tracker(hass) -> None:
    """A person outside a usable zone uses the current source device tracker."""
    hass.states.async_set(
        "person.abbi",
        "not_home",
        {"source": "device_tracker.abbi_phone"},
    )
    hass.states.async_set(
        "device_tracker.abbi_phone",
        "not_home",
        {"latitude": 55.1801, "longitude": -1.6502},
    )

    result = resolve_endpoint(hass, PERSON)

    assert result.latitude == pytest.approx(55.1801)
    assert result.longitude == pytest.approx(-1.6502)


def test_device_tracker_resolves_directly(hass) -> None:
    """A selected device_tracker continues to resolve from its own coordinates."""
    hass.states.async_set(
        "device_tracker.abbi_phone",
        "not_home",
        {"latitude": 55.1801, "longitude": -1.6502},
    )

    result = resolve_endpoint(hass, TRACKER)

    assert result.latitude == pytest.approx(55.1801)
    assert result.longitude == pytest.approx(-1.6502)


def test_person_without_any_trustworthy_location_is_unavailable(hass) -> None:
    """Do not guess when person, zone and source coordinates are all unavailable."""
    hass.states.async_set(
        "person.abbi",
        "not_home",
        {"source": "device_tracker.abbi_phone"},
    )
    hass.states.async_set("device_tracker.abbi_phone", "unavailable")

    with pytest.raises(EndpointUnavailableError):
        resolve_endpoint(hass, PERSON)
