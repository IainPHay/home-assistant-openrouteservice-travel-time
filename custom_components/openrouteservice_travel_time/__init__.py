"""OpenRouteService Travel Time integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenRouteServiceClient
from .const import PLATFORMS
from .coordinator import OpenRouteServiceCoordinator


@dataclass(slots=True)
class OpenRouteServiceRuntimeData:
    """Runtime data for one configured route."""

    client: OpenRouteServiceClient
    coordinator: OpenRouteServiceCoordinator


type OpenRouteServiceConfigEntry = ConfigEntry[OpenRouteServiceRuntimeData]


async def _async_reload_entry(
    hass: HomeAssistant, entry: OpenRouteServiceConfigEntry
) -> None:
    """Reload the route after configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenRouteServiceConfigEntry
) -> bool:
    """Set up one OpenRouteService route."""
    client = OpenRouteServiceClient(
        async_get_clientsession(hass),
        str(entry.data[CONF_API_KEY]),
    )
    coordinator = OpenRouteServiceCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = OpenRouteServiceRuntimeData(
        client=client,
        coordinator=coordinator,
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenRouteServiceConfigEntry
) -> bool:
    """Unload one OpenRouteService route."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
