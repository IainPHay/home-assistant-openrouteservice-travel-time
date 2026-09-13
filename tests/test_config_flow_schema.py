"""Regression tests for config-flow schema rendering."""

from homeassistant.helpers import selector

from custom_components.openrouteservice_travel_time.config_flow import _endpoint_schema
from custom_components.openrouteservice_travel_time.const import (
    CONF_DESTINATION_LOCATION,
    CONF_ORIGIN_LOCATION,
    ENDPOINT_FIXED,
)


def test_fixed_location_selectors_have_frontend_initial_values(hass) -> None:
    """Required location selectors must have defaults so HA can render the form."""
    schema = _endpoint_schema(hass, ENDPOINT_FIXED, ENDPOINT_FIXED)

    validated = schema({})
    expected = {
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
    }

    assert validated[CONF_ORIGIN_LOCATION] == expected
    assert validated[CONF_DESTINATION_LOCATION] == expected

    fields = {str(marker): validator for marker, validator in schema.schema.items()}
    assert isinstance(fields[CONF_ORIGIN_LOCATION], selector.LocationSelector)
    assert isinstance(fields[CONF_DESTINATION_LOCATION], selector.LocationSelector)
