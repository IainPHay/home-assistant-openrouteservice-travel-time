"""Resolve configured route endpoints to current coordinates."""

from __future__ import annotations

from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .const import ENDPOINT_ENTITY
from .models import Coordinates, endpoint_from_config


class EndpointUnavailableError(Exception):
    """A dynamic endpoint cannot currently provide trustworthy coordinates."""


def resolve_endpoint(hass: HomeAssistant, value: object) -> Coordinates:
    """Resolve a fixed point or current entity location."""
    endpoint = endpoint_from_config(value)
    if endpoint.kind != ENDPOINT_ENTITY:
        assert endpoint.coordinates is not None
        return endpoint.coordinates

    assert endpoint.entity_id is not None
    state = hass.states.get(endpoint.entity_id)
    if state is None:
        raise EndpointUnavailableError(
            f"Location entity {endpoint.entity_id} does not exist"
        )
    if state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
        raise EndpointUnavailableError(
            f"Location entity {endpoint.entity_id} is unavailable"
        )

    try:
        return Coordinates(
            latitude=float(state.attributes[ATTR_LATITUDE]),
            longitude=float(state.attributes[ATTR_LONGITUDE]),
        )
    except (KeyError, TypeError, ValueError) as err:
        raise EndpointUnavailableError(
            f"Location entity {endpoint.entity_id} has no usable coordinates"
        ) from err
