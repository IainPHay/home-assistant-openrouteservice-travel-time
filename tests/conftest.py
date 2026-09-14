"""Shared Home Assistant fixtures for OpenRouteService Travel Time tests."""

import pytest

from homeassistant.config_entries import ConfigEntryState

from custom_components.openrouteservice_travel_time.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading integrations from custom_components for every test."""
    return


@pytest.fixture(autouse=True)
async def cleanup_openrouteservice_entries(hass):
    """Unload any route entries created by a test so coordinator timers are cancelled."""
    yield

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
