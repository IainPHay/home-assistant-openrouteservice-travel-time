"""Home Assistant-native config-flow tests for OpenRouteService Travel Time."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType, InvalidData
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
    _build_route_data,
    _error_key,
    _route_signature,
)
from custom_components.openrouteservice_travel_time.const import (
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
)
from custom_components.openrouteservice_travel_time.location import (
    EndpointUnavailableError,
)
from custom_components.openrouteservice_travel_time.models import (
    RouteResult,
    entity_endpoint_config,
    fixed_endpoint_config,
)

ORIGIN = {"latitude": 55.167, "longitude": -1.691}
DESTINATION = {"latitude": 55.172, "longitude": -1.680}


def _start_data(
    *,
    api_key: str = "test-key",
    name: str = "Home to stop",
    origin_type: str = ENDPOINT_FIXED,
    destination_type: str = ENDPOINT_FIXED,
) -> dict:
    return {
        CONF_API_KEY: api_key,
        CONF_NAME: name,
        CONF_ORIGIN_TYPE: origin_type,
        CONF_DESTINATION_TYPE: destination_type,
    }


def _fixed_endpoint_input() -> dict:
    return {
        CONF_ORIGIN_LOCATION: ORIGIN,
        CONF_DESTINATION_LOCATION: DESTINATION,
    }


def _entry_data(
    *,
    api_key: str = "test-key",
    name: str = "Home to stop",
    origin: object | None = None,
    destination: object | None = None,
) -> dict:
    return {
        CONF_API_KEY: api_key,
        CONF_NAME: name,
        CONF_ORIGIN: origin or fixed_endpoint_config(ORIGIN),
        CONF_DESTINATION: destination or fixed_endpoint_config(DESTINATION),
        CONF_PROFILE: DEFAULT_PROFILE,
    }


async def _start_user_flow(hass, start_data: dict | None = None):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    if start_data is None:
        return result
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        start_data,
    )


async def test_user_form(hass) -> None:
    """The integration starts with route identity and endpoint-type choices."""
    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result.get("errors") is None


async def test_fixed_route_user_success(hass) -> None:
    """A valid fixed walking route creates one config entry."""
    result = await _start_user_flow(hass, _start_data())

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "endpoints"

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
            _fixed_endpoint_input(),
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Home to stop"
    assert result2["data"][CONF_PROFILE] == DEFAULT_PROFILE
    assert result2["data"][CONF_API_KEY] == "test-key"
    assert result2["data"][CONF_ORIGIN]["type"] == ENDPOINT_FIXED
    assert result2["data"][CONF_DESTINATION]["type"] == ENDPOINT_FIXED


async def test_dynamic_origin_user_success(hass) -> None:
    """A person can be selected as a dynamic origin."""
    result = await _start_user_flow(
        hass,
        _start_data(origin_type=ENDPOINT_ENTITY),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "endpoints"

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(700.0, 900.0)),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN_ENTITY: "person.iain",
                CONF_DESTINATION_LOCATION: DESTINATION,
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_ORIGIN] == entity_endpoint_config("person.iain")
    assert result2["data"][CONF_DESTINATION] == fixed_endpoint_config(DESTINATION)


def test_build_route_data_supports_dynamic_destination() -> None:
    """Either endpoint can independently follow a location entity."""
    pending = _start_data(
        origin_type=ENDPOINT_FIXED,
        destination_type=ENDPOINT_ENTITY,
    )

    data = _build_route_data(
        pending,
        {
            CONF_ORIGIN_LOCATION: ORIGIN,
            CONF_DESTINATION_ENTITY: "device_tracker.phone",
        },
    )

    assert data[CONF_ORIGIN] == fixed_endpoint_config(ORIGIN)
    assert data[CONF_DESTINATION] == entity_endpoint_config("device_tracker.phone")
    assert data[CONF_PROFILE] == DEFAULT_PROFILE
    assert CONF_ORIGIN_TYPE not in data
    assert CONF_DESTINATION_TYPE not in data


async def test_duplicate_route_aborts(hass) -> None:
    """The same profile and endpoint references cannot be configured twice."""
    existing_data = _entry_data()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing",
        data=existing_data,
        unique_id=_route_signature(existing_data),
    )
    entry.add_to_hass(hass)

    result = await _start_user_flow(hass, _start_data(name="Duplicate"))

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(600.0, 800.0)),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _fixed_endpoint_input(),
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
        (EndpointUnavailableError("missing"), "location_unavailable"),
        (ValueError("coordinates"), "invalid_location"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
def test_error_key_classification(error: Exception, expected: str) -> None:
    """Provider and endpoint failures map to stable translated UI keys."""
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
        (EndpointUnavailableError("missing"), "location_unavailable"),
        (ValueError("coordinates"), "invalid_location"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_endpoint_validation_errors(
    hass, error: Exception, expected: str
) -> None:
    """Validation failures keep the endpoint form open with an actionable error."""
    result = await _start_user_flow(hass, _start_data())

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(side_effect=error),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _fixed_endpoint_input(),
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "endpoints"
    assert result2["errors"] == {"base": expected}


async def test_invalid_dynamic_entity_domain_stays_on_endpoint_form(hass) -> None:
    """Malformed persisted/form data cannot select an unsupported entity domain."""
    result = await _start_user_flow(
        hass,
        _start_data(origin_type=ENDPOINT_ENTITY),
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN_ENTITY: "sensor.latitude",
                CONF_DESTINATION_LOCATION: DESTINATION,
            },
        )


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


async def test_reconfigure_switches_fixed_origin_to_person(hass) -> None:
    """Reconfiguration can switch endpoint type without replacing the API key."""
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Iain to stop",
            CONF_ORIGIN_TYPE: ENDPOINT_ENTITY,
            CONF_DESTINATION_TYPE: ENDPOINT_FIXED,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure_endpoints"

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(720.0, 950.0)),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ORIGIN_ENTITY: "person.iain",
                CONF_DESTINATION_LOCATION: DESTINATION,
            },
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"
    assert entry.title == "Iain to stop"
    assert entry.data[CONF_ORIGIN] == entity_endpoint_config("person.iain")
    assert entry.data[CONF_API_KEY] == "test-key"


async def test_reconfigure_rejects_duplicate_of_another_route(hass) -> None:
    """Reconfiguration cannot collide with another existing route."""
    first_data = _entry_data(
        destination=fixed_endpoint_config(
            {"latitude": 55.175, "longitude": -1.675}
        )
    )
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
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Duplicate",
            CONF_ORIGIN_TYPE: ENDPOINT_FIXED,
            CONF_DESTINATION_TYPE: ENDPOINT_FIXED,
        },
    )

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(return_value=RouteResult(600.0, 800.0)),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ORIGIN_LOCATION: ORIGIN,
                CONF_DESTINATION_LOCATION: {
                    "latitude": 55.175,
                    "longitude": -1.675,
                },
            },
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


async def test_validate_route_uses_current_dynamic_coordinates_and_shared_session(
    hass,
) -> None:
    """Config validation resolves entity state and injects HA's web session."""
    hass.states.async_set(
        "person.iain",
        "not_home",
        {"latitude": 55.25, "longitude": -1.75},
    )
    session = object()
    client = MagicMock()
    client.async_route = AsyncMock(return_value=RouteResult(321.0, 654.0))
    data = _entry_data(origin=entity_endpoint_config("person.iain"))

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
    assert origin.latitude == 55.25
    assert origin.longitude == -1.75
    assert destination.latitude == DESTINATION["latitude"]
    assert destination.longitude == DESTINATION["longitude"]
    assert profile == DEFAULT_PROFILE


async def test_dynamic_reconfigure_prefills_both_entity_endpoints(hass) -> None:
    """Reconfiguring an existing dynamic route restores both entity selections."""
    data = _entry_data(
        origin=entity_endpoint_config("person.iain"),
        destination=entity_endpoint_config("device_tracker.phone"),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Dynamic route",
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
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Dynamic route",
            CONF_ORIGIN_TYPE: ENDPOINT_ENTITY,
            CONF_DESTINATION_TYPE: ENDPOINT_ENTITY,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure_endpoints"
    schema = result2["data_schema"]
    assert schema({}) == {
        CONF_ORIGIN_ENTITY: "person.iain",
        CONF_DESTINATION_ENTITY: "device_tracker.phone",
    }


async def test_endpoint_step_without_pending_data_aborts(hass) -> None:
    """An invalid direct jump to endpoint collection aborts safely."""
    result = await _start_user_flow(hass)
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._pending_data = None

    result2 = await flow.async_step_endpoints()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unknown"


async def test_endpoint_build_error_is_translated(hass) -> None:
    """A canonicalisation failure remains on the endpoint form."""
    result = await _start_user_flow(hass, _start_data())

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._build_route_data",
        side_effect=ValueError("bad endpoint"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _fixed_endpoint_input(),
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_location"}


async def test_reconfigure_endpoint_step_without_pending_data_aborts(hass) -> None:
    """A broken direct jump in reconfiguration aborts safely."""
    data = _entry_data()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Route",
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
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._pending_data = None

    result2 = await flow.async_step_reconfigure_endpoints()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unknown"


async def test_reconfigure_endpoint_build_error_is_translated(hass) -> None:
    """Canonicalisation errors during reconfigure keep the form open."""
    data = _entry_data()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Route",
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
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Route",
            CONF_ORIGIN_TYPE: ENDPOINT_FIXED,
            CONF_DESTINATION_TYPE: ENDPOINT_FIXED,
        },
    )

    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._build_route_data",
        side_effect=ValueError("bad endpoint"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            _fixed_endpoint_input(),
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_location"}


async def test_reconfigure_validation_error_preserves_submitted_endpoints(hass) -> None:
    """Provider validation failure preserves endpoint values for correction."""
    data = _entry_data()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Route",
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
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Route",
            CONF_ORIGIN_TYPE: ENDPOINT_FIXED,
            CONF_DESTINATION_TYPE: ENDPOINT_FIXED,
        },
    )

    changed_destination = {"latitude": 55.19, "longitude": -1.66}
    with patch(
        "custom_components.openrouteservice_travel_time.config_flow._async_validate_route",
        new=AsyncMock(side_effect=OpenRouteServiceNoRouteError("no route")),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ORIGIN_LOCATION: ORIGIN,
                CONF_DESTINATION_LOCATION: changed_destination,
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "no_route"}
    assert result3["data_schema"]({})[CONF_DESTINATION_LOCATION] == changed_destination
