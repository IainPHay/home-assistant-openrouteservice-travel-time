"""Entity, device and diagnostics tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import CONF_API_KEY, CONF_NAME, UnitOfLength, UnitOfTime
from homeassistant.helpers.device_registry import DeviceEntryType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openrouteservice_travel_time import OpenRouteServiceRuntimeData
from custom_components.openrouteservice_travel_time.const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN,
)
from custom_components.openrouteservice_travel_time.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.openrouteservice_travel_time.entity import route_device_info
from custom_components.openrouteservice_travel_time.models import RouteResult
from custom_components.openrouteservice_travel_time.sensor import (
    SENSOR_DESCRIPTIONS,
    OpenRouteServiceSensor,
    async_setup_entry as async_setup_sensors,
)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home to stop",
        data={
            CONF_API_KEY: "super-secret",
            CONF_NAME: "Home to stop",
            CONF_ORIGIN: {"latitude": 55.167, "longitude": -1.691},
            CONF_DESTINATION: {"latitude": 55.172, "longitude": -1.680},
            CONF_PROFILE: DEFAULT_PROFILE,
        },
    )


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = RouteResult(612.5, 845.25)
    coordinator.last_update_success = True
    return coordinator


def test_route_device_is_logical_service() -> None:
    """Configured routes appear as service devices rather than fake hardware."""
    info = route_device_info("entry-id", "Home to stop")

    assert info["identifiers"] == {(DOMAIN, "entry-id")}
    assert info["name"] == "Home to stop"
    assert info["entry_type"] is DeviceEntryType.SERVICE
    assert info["configuration_url"] == "https://openrouteservice.org/"


def test_sensor_metadata_and_values() -> None:
    """Duration and distance use native Home Assistant semantics."""
    entry = _entry()
    coordinator = _coordinator()

    duration = OpenRouteServiceSensor(coordinator, entry, SENSOR_DESCRIPTIONS[0])
    distance = OpenRouteServiceSensor(coordinator, entry, SENSOR_DESCRIPTIONS[1])

    assert duration.native_value == 612.5 / 60
    assert duration.unique_id.endswith("_duration")
    assert duration.device_class is SensorDeviceClass.DURATION
    assert duration.native_unit_of_measurement == UnitOfTime.MINUTES
    assert duration.state_class is SensorStateClass.MEASUREMENT

    assert distance.native_value == 845.25
    assert distance.unique_id.endswith("_distance")
    assert distance.device_class is SensorDeviceClass.DISTANCE
    assert distance.native_unit_of_measurement == UnitOfLength.METERS
    assert distance.state_class is SensorStateClass.MEASUREMENT
    assert distance.device_info["name"] == "Home to stop"


async def test_sensor_platform_adds_both_route_entities(hass) -> None:
    """The sensor platform exposes exactly Duration and Distance initially."""
    entry = _entry()
    coordinator = _coordinator()
    entry.runtime_data = OpenRouteServiceRuntimeData(
        client=MagicMock(),
        coordinator=coordinator,
    )
    add_entities = MagicMock()

    await async_setup_sensors(hass, entry, add_entities)

    entities = list(add_entities.call_args.args[0])
    assert len(entities) == 2
    assert {entity.entity_description.key for entity in entities} == {
        "duration",
        "distance",
    }


async def test_diagnostics_redact_credentials_and_locations(hass) -> None:
    """Diagnostics expose useful route health without secrets or coordinates."""
    entry = _entry()
    coordinator = _coordinator()
    entry.runtime_data = OpenRouteServiceRuntimeData(
        client=MagicMock(),
        coordinator=coordinator,
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    rendered = repr(diagnostics)
    assert "super-secret" not in rendered
    assert "55.167" not in rendered
    assert "-1.691" not in rendered
    assert diagnostics["entry"][CONF_ORIGIN] == "<redacted location>"
    assert diagnostics["entry"][CONF_DESTINATION] == "<redacted location>"
    assert diagnostics["route"] == {
        "duration_seconds": 612.5,
        "distance_metres": 845.25,
    }
    assert diagnostics["last_update_success"] is True


async def test_diagnostics_handle_no_route_data(hass) -> None:
    """Failed/no-data coordinators produce privacy-safe diagnostics."""
    entry = _entry()
    coordinator = _coordinator()
    coordinator.data = None
    coordinator.last_update_success = False
    entry.runtime_data = OpenRouteServiceRuntimeData(
        client=MagicMock(),
        coordinator=coordinator,
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["route"] is None
    assert diagnostics["last_update_success"] is False
