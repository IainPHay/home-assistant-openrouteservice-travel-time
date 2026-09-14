"""OpenRouteService Travel Time integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenRouteServiceClient
from .const import PLATFORMS
from .coordinator import OpenRouteServiceCoordinator

_LOGGER = logging.getLogger(__name__)


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

    # A route is already provider-validated in the config flow. Do not leave a
    # successfully-created entry without entities just because the immediate
    # startup refresh hits a transient network/provider failure. Authentication
    # failures still propagate normally and trigger Home Assistant reauth.
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        _LOGGER.warning(
            "Initial OpenRouteService refresh failed for %s; loading route entities unavailable until the next successful update: %s",
            entry.title,
            err,
        )

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
