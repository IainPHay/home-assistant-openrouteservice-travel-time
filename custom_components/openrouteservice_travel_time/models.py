"""Data models for OpenRouteService Travel Time."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import cast

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE


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
