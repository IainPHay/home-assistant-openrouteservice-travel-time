"""Diagnostics for OpenRouteService Travel Time."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import OpenRouteServiceConfigEntry
from .const import CONF_DESTINATION, CONF_ORIGIN

_TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: OpenRouteServiceConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics without credentials or precise route coordinates."""
    data = async_redact_data(dict(entry.data), _TO_REDACT)
    data[CONF_ORIGIN] = "<redacted location>"
    data[CONF_DESTINATION] = "<redacted location>"
    coordinator = entry.runtime_data.coordinator
    route = coordinator.data
    return {
        "entry": data,
        "last_update_success": coordinator.last_update_success,
        "route": (
            {
                "duration_seconds": route.duration_seconds,
                "distance_metres": route.distance_metres,
            }
            if route is not None
            else None
        ),
    }
