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
from custom_components.openrouteservice_travel_time.models import RouteResult


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home to stop",
        data={
            CONF_API_KEY: "key",
            CONF_NAME: "Home to stop",
            CONF_ORIGIN: {"latitude": 55.167, "longitude": -1.691},
            CONF_DESTINATION: {"latitude": 55.172, "longitude": -1.680},
            CONF_PROFILE: DEFAULT_PROFILE,
        },
    )


def _coordinator(hass):
    entry = _entry()
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_route = AsyncMock()
    return OpenRouteServiceCoordinator(hass, entry, client), client


async def test_update_returns_route_result(hass) -> None:
    """A successful provider result becomes coordinator data."""
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


async def test_invalid_configured_coordinates_are_update_failure(hass) -> None:
    """Invalid coordinates fail the route update without guessing a fallback."""
    entry = _entry()
    entry.data = {
        **entry.data,
        CONF_ORIGIN: {"latitude": "invalid", "longitude": -1.691},
    }
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_route = AsyncMock()
    coordinator = OpenRouteServiceCoordinator(hass, entry, client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    client.async_route.assert_not_awaited()
