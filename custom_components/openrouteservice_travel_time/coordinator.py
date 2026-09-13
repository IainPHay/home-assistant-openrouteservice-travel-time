"""DataUpdateCoordinator for OpenRouteService Travel Time."""

from __future__ import annotations

import logging

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
)
from .location import EndpointUnavailableError, resolve_endpoint
from .models import RouteResult

_LOGGER = logging.getLogger(__name__)


class OpenRouteServiceCoordinator(DataUpdateCoordinator[RouteResult]):
    """Coordinate one configured route."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OpenRouteServiceClient,
    ) -> None:
        """Initialise the route coordinator."""
        self.entry = entry
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.entry_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> RouteResult:
        """Resolve current endpoints and request fresh provider data."""
        try:
            origin = resolve_endpoint(self.hass, self.entry.data[CONF_ORIGIN])
            destination = resolve_endpoint(
                self.hass, self.entry.data[CONF_DESTINATION]
            )
            profile = str(self.entry.data.get(CONF_PROFILE, DEFAULT_PROFILE))
            return await self.client.async_route(origin, destination, profile)
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
