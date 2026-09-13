"""Home Assistant-native config-flow tests for OpenRouteService Travel Time."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openrouteservice_travel_time.api import (
    OpenRouteServiceAuthenticationError,
    OpenRouteServiceConnectionError,
    OpenRouteServiceForbiddenError,
    OpenRouteServiceNoRouteError,
    OpenRouteServiceRateLimitError,
    OpenRouteServiceResponseError,
)
from custom_components.openrouteservice_travel_time.config_flow import (
    _async_validate_route,
    _error_key,
    _route_signature,
)
from custom_components.openrouteservice_travel_time.const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN,
)
from custom_components.openrouteservice_travel_time.models import RouteResult

ORIGIN = {"latitude": 55.167, "longitude": -1.691}
DESTINATION = {"latitude": 55.172, "longitude": -1.680}


def _user_data(
    *,
    api_key: str = "test-key",
    name: str = "Home to stop",
    origin: dict[str, float] | None = None,
    destination: dict[str, float] | None = None,
) -> dict:
    return {
        CONF_API_KEY: api_key,
        CONF_NAME: name,
        CONF_ORIGIN: origin or ORIGIN,
        CONF_DESTINATION: destination or DESTINATION,
    }


def _entry_data(**kwargs) -> dict:
    data = _user_data(**kwargs)
    data[CONF_PROFILE] = DEFAULT_PROFILE
    return data


async def test_user_form(hass) -> None:
    """The integration starts with a UI-only fixed-route form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_success(hass) -> None:
    """A validated walking route creates one config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with (
        patch(
            "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
            new=AsyncMock(return_value=RouteResult(600.0, 800.0)),
        ),
        patch(
            "custom_components.openrouteservice_travel_time.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _user_data(),
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Home to stop"
    assert result2["data"][CONF_PROFILE] == DEFAULT_PROFILE
    assert result2["data"][CONF_API_KEY] == "test-key"


async def test_duplicate_route_aborts(hass) -> None:
    """The same profile/endpoints cannot be configured twice."""
    existing_data = _entry_data()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing",
        data=existing_data,
        unique_id=_route_signature(existing_data),
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(600.0, 800.0)),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _user_data(name="Duplicate"),
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OpenRouteServiceAuthenticationError("bad key"), "invalid_auth"),
        (OpenRouteServiceForbiddenError("forbidden"), "access_forbidden"),
        (OpenRouteServiceRateLimitError("limit"), "rate_limited"),
        (OpenRouteServiceNoRouteError("none"), "no_route"),
        (OpenRouteServiceResponseError("bad"), "invalid_response"),
        (OpenRouteServiceConnectionError("offline"), "cannot_connect"),
        (ValueError("coordinates"), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
def test_error_key_classification(error: Exception, expected: str) -> None:
    """All provider/config errors map to stable translated UI keys."""
    assert _error_key(error) == expected


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OpenRouteServiceAuthenticationError("bad key"), "invalid_auth"),
        (OpenRouteServiceForbiddenError("forbidden"), "access_forbidden"),
        (OpenRouteServiceRateLimitError("limit"), "rate_limited"),
        (OpenRouteServiceNoRouteError("none"), "no_route"),
        (OpenRouteServiceResponseError("bad"), "invalid_response"),
        (OpenRouteServiceConnectionError("offline"), "cannot_connect"),
        (ValueError("coordinates"), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_user_errors(hass, error: Exception, expected: str) -> None:
    """Validation failures keep the config flow open with an actionable error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(side_effect=error),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _user_data(),
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": expected}


async def test_reauth_success(hass) -> None:
    """A confirmed credential failure can replace only the API key."""
    data = _entry_data(api_key="old-key")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home to stop",
        data=data,
        unique_id=_route_signature(data),
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(600.0, 800.0)),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new-key"},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"


async def test_reauth_error_keeps_form_open(hass) -> None:
    """A replacement credential must validate before it is stored."""
    data = _entry_data(api_key="old-key")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home to stop",
        data=data,
        unique_id=_route_signature(data),
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(side_effect=OpenRouteServiceAuthenticationError("bad")),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "still-bad"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_API_KEY] == "old-key"


async def test_reconfigure_success(hass) -> None:
    """Route name/endpoints can be changed without re-entering the API key."""
    data = _entry_data()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home to stop",
        data=data,
        unique_id=_route_signature(data),
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_destination = {"latitude": 55.180, "longitude": -1.670}
    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(720.0, 950.0)),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Updated route",
                CONF_ORIGIN: ORIGIN,
                CONF_DESTINATION: new_destination,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.title == "Updated route"
    assert entry.data[CONF_DESTINATION] == new_destination
    assert entry.data[CONF_API_KEY] == "test-key"


async def test_reconfigure_rejects_duplicate_of_another_route(hass) -> None:
    """Reconfiguration cannot collide with another existing route."""
    first_data = _entry_data(destination={"latitude": 55.175, "longitude": -1.675})
    first = MockConfigEntry(
        domain=DOMAIN,
        title="First",
        data=first_data,
        unique_id=_route_signature(first_data),
    )
    first.add_to_hass(hass)

    target_data = _entry_data()
    target = MockConfigEntry(
        domain=DOMAIN,
        title="Target",
        data=target_data,
        unique_id=_route_signature(target_data),
    )
    target.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": target.entry_id,
        },
    )

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(600.0, 800.0)),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Duplicate",
                CONF_ORIGIN: first_data[CONF_ORIGIN],
                CONF_DESTINATION: first_data[CONF_DESTINATION],
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_validate_route_injects_home_assistant_session(hass) -> None:
    """Route validation uses HA's shared session and the configured route data."""
    session = object()
    client = MagicMock()
    client.async_route = AsyncMock(return_value=RouteResult(321.0, 654.0))
    data = _entry_data()

    with (
        patch(
            "custom_components.openrouteservice_travel_time.config_flow.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.openrouteservice_travel_time.config_flow.OpenRouteServiceClient",
            return_value=client,
        ) as client_cls,
    ):
        result = await _async_validate_route(hass, data)

    assert result == RouteResult(321.0, 654.0)
    client_cls.assert_called_once_with(session, "test-key")
    origin, destination, profile = client.async_route.await_args.args
    assert origin.latitude == ORIGIN["latitude"]
    assert origin.longitude == ORIGIN["longitude"]
    assert destination.latitude == DESTINATION["latitude"]
    assert destination.longitude == DESTINATION["longitude"]
    assert profile == DEFAULT_PROFILE
