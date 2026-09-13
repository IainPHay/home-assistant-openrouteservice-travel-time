"""Config flow for OpenRouteService Travel Time."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OpenRouteServiceAuthenticationError,
    OpenRouteServiceClient,
    OpenRouteServiceConnectionError,
    OpenRouteServiceForbiddenError,
    OpenRouteServiceNoRouteError,
    OpenRouteServiceRateLimitError,
    OpenRouteServiceResponseError,
)
from .const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN,
)
from .models import RouteResult, coordinates_from_config

_LOGGER = logging.getLogger(__name__)

DEFAULT_ROUTE_NAME = "Walking route"


def _location_selector() -> selector.LocationSelector:
    """Return the shared fixed-location selector."""
    return selector.LocationSelector(
        selector.LocationSelectorConfig(radius=False, icon="")
    )


def _route_schema(
    hass: HomeAssistant,
    values: Mapping[str, Any] | None = None,
    *,
    include_api_key: bool,
) -> vol.Schema:
    """Build a route form with visible defaults/suggested values."""
    current = values or {}
    fields: dict[vol.Marker, object] = {}
    if include_api_key:
        fields[vol.Required(CONF_API_KEY)] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )

    fields[vol.Required(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_ROUTE_NAME))] = (
        selector.TextSelector(selector.TextSelectorConfig())
    )
    fields[
        vol.Required(
            CONF_ORIGIN,
            default=current.get(
                CONF_ORIGIN,
                {
                    CONF_LATITUDE: hass.config.latitude,
                    CONF_LONGITUDE: hass.config.longitude,
                },
            ),
        )
    ] = _location_selector()

    if CONF_DESTINATION in current:
        destination_marker = vol.Required(
            CONF_DESTINATION, default=current[CONF_DESTINATION]
        )
    else:
        destination_marker = vol.Required(CONF_DESTINATION)
    fields[destination_marker] = _location_selector()

    return vol.Schema(fields)


def _api_key_schema() -> vol.Schema:
    """Return the reauthentication form schema."""
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        }
    )


def _route_signature(data: Mapping[str, Any]) -> str:
    """Return a stable signature for duplicate-route prevention."""
    origin = coordinates_from_config(data[CONF_ORIGIN])
    destination = coordinates_from_config(data[CONF_DESTINATION])
    profile = str(data.get(CONF_PROFILE, DEFAULT_PROFILE))
    return (
        f"{profile}:"
        f"{origin.latitude:.6f},{origin.longitude:.6f}:"
        f"{destination.latitude:.6f},{destination.longitude:.6f}"
    )


def _duplicate_route(
    flow: ConfigFlow,
    signature: str,
    *,
    ignore_entry_id: str | None = None,
) -> bool:
    """Return whether another current entry already represents this route."""
    return any(
        entry.entry_id != ignore_entry_id and entry.unique_id == signature
        for entry in flow._async_current_entries()
    )


async def _async_validate_route(
    hass: HomeAssistant,
    data: Mapping[str, Any],
) -> RouteResult:
    """Validate credentials and route inputs using a real route request."""
    origin = coordinates_from_config(data[CONF_ORIGIN])
    destination = coordinates_from_config(data[CONF_DESTINATION])
    client = OpenRouteServiceClient(
        async_get_clientsession(hass),
        str(data[CONF_API_KEY]),
    )
    return await client.async_route(
        origin,
        destination,
        str(data.get(CONF_PROFILE, DEFAULT_PROFILE)),
    )


def _error_key(err: Exception) -> str:
    """Map provider exceptions to translated config-flow errors."""
    if isinstance(err, OpenRouteServiceAuthenticationError):
        return "invalid_auth"
    if isinstance(err, OpenRouteServiceForbiddenError):
        return "access_forbidden"
    if isinstance(err, OpenRouteServiceRateLimitError):
        return "rate_limited"
    if isinstance(err, OpenRouteServiceNoRouteError):
        return "no_route"
    if isinstance(err, OpenRouteServiceResponseError):
        return "invalid_response"
    if isinstance(err, (OpenRouteServiceConnectionError, ValueError)):
        return "cannot_connect"
    return "unknown"


class OpenRouteServiceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle OpenRouteService Travel Time configuration."""

    VERSION = 1

    async def _validate(
        self, data: Mapping[str, Any]
    ) -> tuple[bool, dict[str, str]]:
        """Validate route data and convert failures to UI errors."""
        try:
            await _async_validate_route(self.hass, data)
        except (
            OpenRouteServiceAuthenticationError,
            OpenRouteServiceForbiddenError,
            OpenRouteServiceRateLimitError,
            OpenRouteServiceNoRouteError,
            OpenRouteServiceResponseError,
            OpenRouteServiceConnectionError,
            ValueError,
        ) as err:
            return False, {"base": _error_key(err)}
        except Exception:
            _LOGGER.exception("Unexpected exception while validating route")
            return False, {"base": "unknown"}
        return True, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure one fixed-coordinate walking route."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            data[CONF_PROFILE] = DEFAULT_PROFILE
            valid, errors = await self._validate(data)
            if valid:
                signature = _route_signature(data)
                await self.async_set_unique_id(signature)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=str(data[CONF_NAME]),
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_route_schema(
                self.hass,
                user_input,
                include_api_key=True,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after a confirmed credential failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and replace the API key."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = dict(entry.data)
            data[CONF_API_KEY] = user_input[CONF_API_KEY]
            valid, errors = await self._validate(data)
            if valid:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_api_key_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure route name and fixed endpoints."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            data = dict(entry.data)
            data.update(user_input)
            data[CONF_PROFILE] = DEFAULT_PROFILE
            valid, errors = await self._validate(data)
            if valid:
                signature = _route_signature(data)
                if _duplicate_route(
                    self,
                    signature,
                    ignore_entry_id=entry.entry_id,
                ):
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=signature,
                    title=str(data[CONF_NAME]),
                    data=data,
                )

        current = {
            CONF_NAME: entry.data[CONF_NAME],
            CONF_ORIGIN: entry.data[CONF_ORIGIN],
            CONF_DESTINATION: entry.data[CONF_DESTINATION],
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_route_schema(
                self.hass,
                current,
                include_api_key=False,
            ),
            errors=errors,
        )
