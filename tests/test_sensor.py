"""Sensor presentation tests for OpenRouteService Travel Time."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfLength, UnitOfTime

from custom_components.openrouteservice_travel_time.sensor import (
    SENSOR_DESCRIPTIONS,
    duration_minutes,
)


def _description(key: str):
    return next(item for item in SENSOR_DESCRIPTIONS if item.key == key)


def test_duration_uses_whole_minute_presentation() -> None:
    """Duration is exposed in minutes with zero suggested decimal places."""
    description = _description("duration")

    assert description.device_class is SensorDeviceClass.DURATION
    assert description.native_unit_of_measurement == UnitOfTime.MINUTES
    assert description.suggested_display_precision == 0
    assert duration_minutes(240.8) == 240.8 / 60.0


def test_distance_uses_metre_presentation_without_decimals() -> None:
    """Walking distance remains native metres with a clean whole-metre display."""
    description = _description("distance")

    assert description.device_class is SensorDeviceClass.DISTANCE
    assert description.native_unit_of_measurement == UnitOfLength.METERS
    assert description.suggested_display_precision == 0
