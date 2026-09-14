"""Home Assistant lifecycle tests for OpenRouteService Travel Time."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openrouteservice_travel_time import (
    OpenRouteServiceRuntimeData,
    _async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.openrouteservice_travel_time.const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN,
    PLATFORMS,
)


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


async def test_setup_entry_uses_shared_session_and_first_refresh(hass) -> None:
    """Setup injects Home Assistant's session and verifies the route first."""
    entry = _entry()
    entry.add_to_hass(hass)
    session = MagicMock()
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.openrouteservice_travel_time.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.openrouteservice_travel_time.OpenRouteServiceCoordinator",
            return_value=coordinator,
        ) as coordinator_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward,
    ):
        assert await async_setup_entry(hass, entry) is True

    coordinator_cls.assert_called_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    forward.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.runtime_data.coordinator is coordinator
    assert entry.runtime_data.client.session is session
    assert entry.runtime_data.client.api_key == "key"


async def test_setup_entry_loads_entities_after_transient_first_refresh_failure(
    hass,
) -> None:
    """A transient initial provider failure must not leave a route with no entities."""
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=ConfigEntryNotReady("temporary provider failure")
    )

    with (
        patch(
            "custom_components.openrouteservice_travel_time.OpenRouteServiceCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward,
    ):
        assert await async_setup_entry(hass, entry) is True

    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    forward.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.runtime_data.coordinator is coordinator


async def test_unload_entry_unloads_platforms(hass) -> None:
    """Unloading a route delegates cleanly to Home Assistant platforms."""
    entry = _entry()
    entry.add_to_hass(hass)
    entry.runtime_data = OpenRouteServiceRuntimeData(
        client=MagicMock(),
        coordinator=MagicMock(),
    )

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ) as unload:
        assert await async_unload_entry(hass, entry) is True

    unload.assert_awaited_once_with(entry, PLATFORMS)


async def test_reload_listener_reloads_entry(hass) -> None:
    """Config-entry changes reload the route."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_reload",
        new=AsyncMock(return_value=True),
    ) as reload_entry:
        await _async_reload_entry(hass, entry)

    reload_entry.assert_awaited_once_with(entry.entry_id)
