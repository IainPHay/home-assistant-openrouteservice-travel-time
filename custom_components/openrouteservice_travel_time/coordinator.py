"""DataUpdateCoordinator for OpenRouteService Travel Time."""

from __future__ import annotations

import logging
import math
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    OpenRouteServiceAuthenticationError,
    OpenRouteServiceClient,
    OpenRouteServiceError,
)
from .const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MINIMUM_PROVIDER_REQUEST_INTERVAL,
    MINIMUM_ROUTE_CHANGE_METRES,
    ROUTE_CACHE_TTL,
)
from .location import EndpointUnavailableError, resolve_endpoint
from .models import Coordinates, RouteResult

_LOGGER = logging.getLogger(__name__)
_EARTH_RADIUS_METRES = 6_371_000.0


def _distance_metres(first: Coordinates, second: Coordinates) -> float:
    """Return great-circle distance between two coordinates in metres."""
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(second.longitude - first.longitude)
    haversine = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2.0) ** 2
    )
    return 2.0 * _EARTH_RADIUS_METRES * math.atan2(
        math.sqrt(haversine),
        math.sqrt(1.0 - haversine),
    )


class OpenRouteServiceCoordinator(DataUpdateCoordinator[RouteResult]):
    """Coordinate one configured route with provider quota protection."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OpenRouteServiceClient,
    ) -> None:
        """Initialise the route coordinator."""
        self.entry = entry
        self.client = client
        self._last_provider_request: float | None = None
        self._last_origin: Coordinates | None = None
        self._last_destination: Coordinates | None = None
        self._last_result: RouteResult | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.entry_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    def _can_reuse_cached_result(
        self,
        origin: Coordinates,
        destination: Coordinates,
        now: float,
    ) -> bool:
        """Return whether the previous provider result is still trustworthy."""
        if (
            self._last_result is None
            or self._last_provider_request is None
            or self._last_origin is None
            or self._last_destination is None
        ):
            return False

        elapsed = now - self._last_provider_request

        # This is the hard provider-call ceiling. Even repeated manual entity
        # refreshes cannot make this config entry call ORS more often.
        if elapsed < MINIMUM_PROVIDER_REQUEST_INTERVAL.total_seconds():
            return True

        if elapsed >= ROUTE_CACHE_TTL.total_seconds():
            return False

        origin_change = _distance_metres(origin, self._last_origin)
        destination_change = _distance_metres(destination, self._last_destination)
        return (
            origin_change < MINIMUM_ROUTE_CHANGE_METRES
            and destination_change < MINIMUM_ROUTE_CHANGE_METRES
        )

    async def _async_update_data(self) -> RouteResult:
        """Resolve endpoints and request ORS only when quota policy permits."""
        try:
            origin = resolve_endpoint(self.hass, self.entry.data[CONF_ORIGIN])
            destination = resolve_endpoint(
                self.hass, self.entry.data[CONF_DESTINATION]
            )
            now = time.monotonic()
            if self._can_reuse_cached_result(origin, destination, now):
                assert self._last_result is not None
                return self._last_result

            profile = str(self.entry.data.get(CONF_PROFILE, DEFAULT_PROFILE))
            result = await self.client.async_route(origin, destination, profile)
            self._last_provider_request = now
            self._last_origin = origin
            self._last_destination = destination
            self._last_result = result
            return result
        except OpenRouteServiceAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except EndpointUnavailableError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            raise UpdateFailed("Configured route endpoint is invalid") from err
        except OpenRouteServiceError as err:
            raise UpdateFailed(str(err)) from err
