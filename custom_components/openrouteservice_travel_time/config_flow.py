"""Config flow for OpenRouteService Travel Time."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME
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
    CONF_DESTINATION_ENTITY,
    CONF_DESTINATION_LOCATION,
    CONF_DESTINATION_TYPE,
    CONF_ORIGIN,
    CONF_ORIGIN_ENTITY,
    CONF_ORIGIN_LOCATION,
    CONF_ORIGIN_TYPE,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN,
    ENDPOINT_ENTITY,
    ENDPOINT_FIXED,
    LOCATION_ENTITY_DOMAINS,
)
from .location import EndpointUnavailableError, resolve_endpoint
from .models import (
    RouteResult,
    endpoint_from_config,
    endpoint_signature,
    entity_endpoint_config,
    fixed_endpoint_config,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_ROUTE_NAME = "Walking route"


def _endpoint_type_selector() -> selector.SelectSelector:
    """Return the fixed/dynamic endpoint selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[ENDPOINT_FIXED, ENDPOINT_ENTITY],
            translation_key="endpoint_type",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _start_schema(
    values: Mapping[str, Any] | None = None,
    *,
    include_api_key: bool,
) -> vol.Schema:
    """Build the route name and endpoint-type form."""
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
            CONF_ORIGIN_TYPE,
            default=current.get(CONF_ORIGIN_TYPE, ENDPOINT_FIXED),
        )
    ] = _endpoint_type_selector()
    fields[
        vol.Required(
            CONF_DESTINATION_TYPE,
            default=current.get(CONF_DESTINATION_TYPE, ENDPOINT_FIXED),
        )
    ] = _endpoint_type_selector()
    return vol.Schema(fields)


def _location_selector() -> selector.LocationSelector:
    """Return a fixed-location selector."""
    return selector.LocationSelector(
        selector.LocationSelectorConfig(radius=False, icon="")
    )


def _entity_selector() -> selector.EntitySelector:
    """Return a selector restricted to location-capable entity domains."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=list(LOCATION_ENTITY_DOMAINS))
    )


def _endpoint_schema(
    hass: HomeAssistant,
    origin_type: str,
    destination_type: str,
    values: Mapping[str, Any] | None = None,
) -> vol.Schema:
    """Build fields for the chosen endpoint types."""
    current = values or {}
    fields: dict[vol.Marker, object] = {}

    if origin_type == ENDPOINT_ENTITY:
        marker = vol.Required(CONF_ORIGIN_ENTITY)
        if CONF_ORIGIN_ENTITY in current:
            marker = vol.Required(
                CONF_ORIGIN_ENTITY,
                default=current[CONF_ORIGIN_ENTITY],
            )
        fields[marker] = _entity_selector()
    else:
        origin_default = current.get(
            CONF_ORIGIN_LOCATION,
            {
                "latitude": hass.config.latitude,
                "longitude": hass.config.longitude,
            },
        )
        fields[
            vol.Required(CONF_ORIGIN_LOCATION, default=origin_default)
        ] = _location_selector()

    if destination_type == ENDPOINT_ENTITY:
        marker = vol.Required(CONF_DESTINATION_ENTITY)
        if CONF_DESTINATION_ENTITY in current:
            marker = vol.Required(
                CONF_DESTINATION_ENTITY,
                default=current[CONF_DESTINATION_ENTITY],
            )
        fields[marker] = _entity_selector()
    else:
        # Required location selectors need an initial value for Home Assistant's
        # frontend form initialisation. Without one the config-flow form can render
        # blank before the selector itself is displayed.
        destination_default = current.get(
            CONF_DESTINATION_LOCATION,
            {
                "latitude": hass.config.latitude,
                "longitude": hass.config.longitude,
            },
        )
        fields[
            vol.Required(CONF_DESTINATION_LOCATION, default=destination_default)
        ] = _location_selector()

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


def _endpoint_type(value: object) -> str:
    """Return the persisted endpoint type."""
    return endpoint_from_config(value).kind


def _endpoint_form_defaults(data: Mapping[str, Any]) -> dict[str, Any]:
    """Convert persisted endpoints back into UI field defaults."""
    defaults: dict[str, Any] = {}
    origin = endpoint_from_config(data[CONF_ORIGIN])
    if origin.kind == ENDPOINT_ENTITY:
        assert origin.entity_id is not None
        defaults[CONF_ORIGIN_ENTITY] = origin.entity_id
    else:
        assert origin.coordinates is not None
        defaults[CONF_ORIGIN_LOCATION] = {
            "latitude": origin.coordinates.latitude,
            "longitude": origin.coordinates.longitude,
        }

    destination = endpoint_from_config(data[CONF_DESTINATION])
    if destination.kind == ENDPOINT_ENTITY:
        assert destination.entity_id is not None
        defaults[CONF_DESTINATION_ENTITY] = destination.entity_id
    else:
        assert destination.coordinates is not None
        defaults[CONF_DESTINATION_LOCATION] = {
            "latitude": destination.coordinates.latitude,
            "longitude": destination.coordinates.longitude,
        }
    return defaults


def _build_route_data(
    pending: Mapping[str, Any],
    endpoint_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Build canonical persisted route data from the two UI steps."""
    data = {
        key: value
        for key, value in pending.items()
        if key not in {CONF_ORIGIN_TYPE, CONF_DESTINATION_TYPE}
    }

    if pending[CONF_ORIGIN_TYPE] == ENDPOINT_ENTITY:
        data[CONF_ORIGIN] = entity_endpoint_config(
            str(endpoint_input[CONF_ORIGIN_ENTITY])
        )
    else:
        data[CONF_ORIGIN] = fixed_endpoint_config(
            endpoint_input[CONF_ORIGIN_LOCATION]
        )

    if pending[CONF_DESTINATION_TYPE] == ENDPOINT_ENTITY:
        data[CONF_DESTINATION] = entity_endpoint_config(
            str(endpoint_input[CONF_DESTINATION_ENTITY])
        )
    else:
        data[CONF_DESTINATION] = fixed_endpoint_config(
            endpoint_input[CONF_DESTINATION_LOCATION]
        )

    data[CONF_PROFILE] = DEFAULT_PROFILE
    return data


def _route_signature(data: Mapping[str, Any]) -> str:
    """Return a stable route identity that does not track moving coordinates."""
    profile = str(data.get(CONF_PROFILE, DEFAULT_PROFILE))
    return (
        f"{profile}:"
        f"{endpoint_signature(data[CONF_ORIGIN])}:"
        f"{endpoint_signature(data[CONF_DESTINATION])}"
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
    """Validate current endpoint coordinates and provider access."""
    origin = resolve_endpoint(hass, data[CONF_ORIGIN])
    destination = resolve_endpoint(hass, data[CONF_DESTINATION])
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
    """Map provider and endpoint exceptions to translated config-flow errors."""
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
    if isinstance(err, EndpointUnavailableError):
        return "location_unavailable"
    if isinstance(err, ValueError):
        return "invalid_location"
    if isinstance(err, OpenRouteServiceConnectionError):
        return "cannot_connect"
    return "unknown"


class OpenRouteServiceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle OpenRouteService Travel Time configuration."""

    VERSION = 1

    _pending_data: dict[str, Any] | None = None
    _endpoint_defaults: dict[str, Any] | None = None

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
            EndpointUnavailableError,
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
        """Collect route identity and endpoint types."""
        if user_input is not None:
            self._pending_data = dict(user_input)
            self._endpoint_defaults = {}
            return await self.async_step_endpoints()

        return self.async_show_form(
            step_id="user",
            data_schema=_start_schema(include_api_key=True),
        )

    async def async_step_endpoints(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect fixed locations or dynamic Home Assistant entities."""
        if self._pending_data is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = _build_route_data(self._pending_data, user_input)
            except ValueError as err:
                errors["base"] = _error_key(err)
            else:
                valid, errors = await self._validate(data)
                if valid:
                    signature = _route_signature(data)
                    await self.async_set_unique_id(signature)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=str(data[CONF_NAME]),
                        data=data,
                    )
            self._endpoint_defaults = dict(user_input)

        return self.async_show_form(
            step_id="endpoints",
            data_schema=_endpoint_schema(
                self.hass,
                str(self._pending_data[CONF_ORIGIN_TYPE]),
                str(self._pending_data[CONF_DESTINATION_TYPE]),
                self._endpoint_defaults,
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
        """Collect updated route identity and endpoint types."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._pending_data = {
                **dict(entry.data),
                CONF_NAME: user_input[CONF_NAME],
                CONF_ORIGIN_TYPE: user_input[CONF_ORIGIN_TYPE],
                CONF_DESTINATION_TYPE: user_input[CONF_DESTINATION_TYPE],
            }
            self._endpoint_defaults = _endpoint_form_defaults(entry.data)
            return await self.async_step_reconfigure_endpoints()

        values = {
            CONF_NAME: entry.data[CONF_NAME],
            CONF_ORIGIN_TYPE: _endpoint_type(entry.data[CONF_ORIGIN]),
            CONF_DESTINATION_TYPE: _endpoint_type(entry.data[CONF_DESTINATION]),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_start_schema(values, include_api_key=False),
        )

    async def async_step_reconfigure_endpoints(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and persist reconfigured endpoints."""
        if self._pending_data is None:
            return self.async_abort(reason="unknown")

        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = _build_route_data(self._pending_data, user_input)
            except ValueError as err:
                errors["base"] = _error_key(err)
            else:
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
            self._endpoint_defaults = dict(user_input)

        return self.async_show_form(
            step_id="reconfigure_endpoints",
            data_schema=_endpoint_schema(
                self.hass,
                str(self._pending_data[CONF_ORIGIN_TYPE]),
                str(self._pending_data[CONF_DESTINATION_TYPE]),
                self._endpoint_defaults,
            ),
            errors=errors,
        )
