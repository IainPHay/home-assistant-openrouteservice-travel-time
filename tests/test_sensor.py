"""Sensor presentation tests for OpenRouteService Travel Time."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfLength, UnitOfTime

from custom_components.openrouteservice_travel_time.sensor import (
    SENSOR_DESCRIPTIONS,
    distance_kilometres,
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


def test_distance_uses_kilometre_presentation_with_one_decimal() -> None:
    """Distance is exposed in kilometres with one suggested decimal place."""
    description = _description("distance")

    assert description.device_class is SensorDeviceClass.DISTANCE
    assert description.native_unit_of_measurement == UnitOfLength.KILOMETERS
    assert description.suggested_display_precision == 1
    assert distance_kilometres(22_204.0) == 22.204
