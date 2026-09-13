"""Data models for OpenRouteService Travel Time."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Literal, cast

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import (
    CONF_ENDPOINT_ENTITY_ID,
    CONF_ENDPOINT_TYPE,
    ENDPOINT_ENTITY,
    ENDPOINT_FIXED,
    LOCATION_ENTITY_DOMAINS,
)

type EndpointKind = Literal["fixed", "entity"]


@dataclass(frozen=True, slots=True)
class Coordinates:
    """A geographic point stored in Home Assistant latitude/longitude order."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """Validate coordinate ranges and finite values."""
        if not math.isfinite(self.latitude) or not -90 <= self.latitude <= 90:
            raise ValueError("Latitude must be finite and between -90 and 90")
        if not math.isfinite(self.longitude) or not -180 <= self.longitude <= 180:
            raise ValueError("Longitude must be finite and between -180 and 180")

    @property
    def ors_pair(self) -> list[float]:
        """Return OpenRouteService longitude/latitude coordinate order."""
        return [self.longitude, self.latitude]


@dataclass(frozen=True, slots=True)
class RouteEndpoint:
    """A fixed point or a Home Assistant entity used as a route endpoint."""

    kind: EndpointKind
    coordinates: Coordinates | None = None
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class RouteResult:
    """The provider-neutral values exposed by one route update."""

    duration_seconds: float
    distance_metres: float


def coordinates_from_config(value: object) -> Coordinates:
    """Convert a Home Assistant location-selector value to coordinates."""
    if not isinstance(value, Mapping):
        raise ValueError("Location must contain latitude and longitude")
    location = cast(Mapping[str, object], value)
    latitude = location.get(CONF_LATITUDE)
    longitude = location.get(CONF_LONGITUDE)
    if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
        raise ValueError("Location latitude is invalid")
    if isinstance(longitude, bool) or not isinstance(longitude, (int, float)):
        raise ValueError("Location longitude is invalid")
    return Coordinates(float(latitude), float(longitude))


def _validate_location_entity_id(entity_id: str) -> str:
    """Validate the supported Home Assistant location-entity domains."""
    domain, separator, object_id = entity_id.partition(".")
    if separator != "." or not object_id or domain not in LOCATION_ENTITY_DOMAINS:
        raise ValueError(
            "Location entity must be a person or device_tracker entity"
        )
    return entity_id


def endpoint_from_config(value: object) -> RouteEndpoint:
    """Decode a persisted route endpoint, including alpha.1 fixed locations."""
    if not isinstance(value, Mapping):
        raise ValueError("Route endpoint must be an object")

    endpoint = cast(Mapping[str, object], value)
    endpoint_type = endpoint.get(CONF_ENDPOINT_TYPE)

    # alpha.1 stored the location-selector mapping directly.
    if endpoint_type is None and (
        CONF_LATITUDE in endpoint or CONF_LONGITUDE in endpoint
    ):
        return RouteEndpoint(
            kind=ENDPOINT_FIXED,
            coordinates=coordinates_from_config(endpoint),
        )

    if endpoint_type == ENDPOINT_FIXED:
        return RouteEndpoint(
            kind=ENDPOINT_FIXED,
            coordinates=coordinates_from_config(endpoint),
        )

    if endpoint_type == ENDPOINT_ENTITY:
        entity_id = endpoint.get(CONF_ENDPOINT_ENTITY_ID)
        if not isinstance(entity_id, str):
            raise ValueError("Location entity ID is missing")
        return RouteEndpoint(
            kind=ENDPOINT_ENTITY,
            entity_id=_validate_location_entity_id(entity_id),
        )

    raise ValueError("Route endpoint type is invalid")


def fixed_endpoint_config(value: object) -> dict[str, object]:
    """Return canonical persisted data for a fixed endpoint."""
    coordinates = coordinates_from_config(value)
    return {
        CONF_ENDPOINT_TYPE: ENDPOINT_FIXED,
        CONF_LATITUDE: coordinates.latitude,
        CONF_LONGITUDE: coordinates.longitude,
    }


def entity_endpoint_config(entity_id: str) -> dict[str, object]:
    """Return canonical persisted data for a dynamic entity endpoint."""
    return {
        CONF_ENDPOINT_TYPE: ENDPOINT_ENTITY,
        CONF_ENDPOINT_ENTITY_ID: _validate_location_entity_id(entity_id),
    }


def endpoint_signature(value: object) -> str:
    """Return a stable identity component without using moving coordinates."""
    endpoint = endpoint_from_config(value)
    if endpoint.kind == ENDPOINT_ENTITY:
        assert endpoint.entity_id is not None
        return f"entity:{endpoint.entity_id}"

    assert endpoint.coordinates is not None
    return (
        "fixed:"
        f"{endpoint.coordinates.latitude:.6f},"
        f"{endpoint.coordinates.longitude:.6f}"
    )
