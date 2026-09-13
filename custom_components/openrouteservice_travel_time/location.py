"""Resolve configured route endpoints to current coordinates."""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State

from .const import ENDPOINT_ENTITY
from .models import Coordinates, endpoint_from_config

ATTR_IN_ZONES = "in_zones"
ATTR_SOURCE = "source"
PERSON_DOMAIN = "person"
ZONE_DOMAIN = "zone"


class EndpointUnavailableError(Exception):
    """A dynamic endpoint cannot currently provide trustworthy coordinates."""


def _coordinates_from_state(state: State) -> Coordinates | None:
    """Return coordinates from a state when both attributes are usable."""
    try:
        return Coordinates(
            latitude=float(state.attributes[ATTR_LATITUDE]),
            longitude=float(state.attributes[ATTR_LONGITUDE]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _normalise_zone_name(value: str) -> str:
    """Normalise a zone/state label for conservative matching."""
    return value.strip().casefold().replace(" ", "_")


def _iter_person_zone_ids(state: State) -> Iterable[str]:
    """Yield Home Assistant zone entity IDs explicitly reported by a person."""
    zones = state.attributes.get(ATTR_IN_ZONES)
    if not isinstance(zones, list):
        return ()
    return tuple(
        zone_id
        for zone_id in zones
        if isinstance(zone_id, str) and zone_id.startswith(f"{ZONE_DOMAIN}.")
    )


def _resolve_person_zone(hass: HomeAssistant, state: State) -> Coordinates | None:
    """Resolve a person's current Home Assistant zone to zone coordinates."""
    zone_ids = tuple(_iter_person_zone_ids(state))
    if not zone_ids:
        return None

    person_zone = _normalise_zone_name(state.state)
    candidates: list[State] = []
    for zone_id in zone_ids:
        zone_state = hass.states.get(zone_id)
        if zone_state is None:
            continue
        candidates.append(zone_state)

        object_id = zone_id.partition(".")[2]
        friendly_name = zone_state.attributes.get(ATTR_FRIENDLY_NAME)
        names = {_normalise_zone_name(object_id)}
        if isinstance(friendly_name, str):
            names.add(_normalise_zone_name(friendly_name))
        if person_zone in names:
            return _coordinates_from_state(zone_state)

    # If Home Assistant explicitly reports exactly one containing zone, it is a
    # trustworthy fallback even when the person's display state does not match
    # the zone entity_id/friendly name byte-for-byte.
    if len(candidates) == 1:
        return _coordinates_from_state(candidates[0])
    return None


def _resolve_person_source(hass: HomeAssistant, state: State) -> Coordinates | None:
    """Resolve the device_tracker currently selected as a person's source."""
    source = state.attributes.get(ATTR_SOURCE)
    if not isinstance(source, str):
        return None
    source_state = hass.states.get(source)
    if source_state is None or source_state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
        return None
    return _coordinates_from_state(source_state)


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

    direct = _coordinates_from_state(state)
    if direct is not None:
        return direct

    if endpoint.entity_id.startswith(f"{PERSON_DOMAIN}."):
        zone = _resolve_person_zone(hass, state)
        if zone is not None:
            return zone

        source = _resolve_person_source(hass, state)
        if source is not None:
            return source

    raise EndpointUnavailableError(
        f"Location entity {endpoint.entity_id} has no usable coordinates"
    )
