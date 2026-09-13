"""Coordinator tests for OpenRouteService Travel Time."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openrouteservice_travel_time.api import (
    OpenRouteServiceAuthenticationError,
    OpenRouteServiceForbiddenError,
)
from custom_components.openrouteservice_travel_time.const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from custom_components.openrouteservice_travel_time.coordinator import (
    OpenRouteServiceCoordinator,
)
from custom_components.openrouteservice_travel_time.models import (
    RouteResult,
    entity_endpoint_config,
    fixed_endpoint_config,
)

FIXED_ORIGIN = {"latitude": 55.167, "longitude": -1.691}
FIXED_DESTINATION = {"latitude": 55.172, "longitude": -1.680}


def _entry(
    *,
    origin: object | None = None,
    destination: object | None = None,
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home to stop",
        data={
            CONF_API_KEY: "key",
            CONF_NAME: "Home to stop",
            CONF_ORIGIN: origin or fixed_endpoint_config(FIXED_ORIGIN),
            CONF_DESTINATION: destination
            or fixed_endpoint_config(FIXED_DESTINATION),
            CONF_PROFILE: DEFAULT_PROFILE,
        },
    )


def _coordinator(hass, *, entry: MockConfigEntry | None = None):
    route_entry = entry or _entry()
    route_entry.add_to_hass(hass)
    client = MagicMock()
    client.async_route = AsyncMock()
    return OpenRouteServiceCoordinator(hass, route_entry, client), client


async def test_fixed_update_returns_route_result(hass) -> None:
    """A successful fixed provider result becomes coordinator data."""
    coordinator, client = _coordinator(hass)
    client.async_route.return_value = RouteResult(600.0, 800.0)

    result = await coordinator._async_update_data()

    assert result == RouteResult(600.0, 800.0)
    origin, destination, profile = client.async_route.await_args.args
    assert origin.latitude == 55.167
    assert origin.longitude == -1.691
    assert destination.latitude == 55.172
    assert destination.longitude == -1.680
    assert profile == DEFAULT_PROFILE
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL


async def test_dynamic_origin_is_resolved_on_each_update(hass) -> None:
    """A moving person is resolved immediately before every provider request."""
    entry = _entry(origin=entity_endpoint_config("person.iain"))
    coordinator, client = _coordinator(hass, entry=entry)
    client.async_route.return_value = RouteResult(500.0, 700.0)

    hass.states.async_set(
        "person.iain",
        "not_home",
        {"latitude": 55.20, "longitude": -1.70},
    )
    await coordinator._async_update_data()
    first_origin = client.async_route.await_args.args[0]

    hass.states.async_set(
        "person.iain",
        "not_home",
        {"latitude": 55.30, "longitude": -1.80},
    )
    await coordinator._async_update_data()
    second_origin = client.async_route.await_args.args[0]

    assert (first_origin.latitude, first_origin.longitude) == (55.20, -1.70)
    assert (second_origin.latitude, second_origin.longitude) == (55.30, -1.80)
    assert client.async_route.await_count == 2


async def test_alpha1_fixed_endpoint_remains_supported(hass) -> None:
    """Existing alpha.1 direct location mappings still resolve."""
    entry = _entry(origin=FIXED_ORIGIN, destination=FIXED_DESTINATION)
    coordinator, client = _coordinator(hass, entry=entry)
    client.async_route.return_value = RouteResult(600.0, 800.0)

    result = await coordinator._async_update_data()

    assert result.duration_seconds == 600.0
    assert client.async_route.await_args.args[0].latitude == 55.167


async def test_authentication_failure_requests_reauth(hass) -> None:
    """Only an explicitly classified authentication failure becomes reauth."""
    coordinator, client = _coordinator(hass)
    client.async_route.side_effect = OpenRouteServiceAuthenticationError("bad key")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_provider_failure_is_transient_update_failure(hass) -> None:
    """A non-auth provider failure does not invalidate credentials."""
    coordinator, client = _coordinator(hass)
    client.async_route.side_effect = OpenRouteServiceForbiddenError("forbidden")

    with pytest.raises(UpdateFailed, match="forbidden"):
        await coordinator._async_update_data()


async def test_dynamic_entity_unavailable_is_update_failure(hass) -> None:
    """Missing dynamic coordinates make entities unavailable without API traffic."""
    entry = _entry(origin=entity_endpoint_config("person.iain"))
    coordinator, client = _coordinator(hass, entry=entry)

    with pytest.raises(UpdateFailed, match="does not exist"):
        await coordinator._async_update_data()

    client.async_route.assert_not_awaited()


async def test_invalid_configured_endpoint_is_update_failure(hass) -> None:
    """Invalid persisted endpoint data fails safely without provider traffic."""
    entry = _entry(origin={"type": "fixed", "latitude": "invalid", "longitude": -1.691})
    coordinator, client = _coordinator(hass, entry=entry)

    with pytest.raises(UpdateFailed, match="Configured route endpoint is invalid"):
        await coordinator._async_update_data()

    client.async_route.assert_not_awaited()
