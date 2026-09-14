"""Sensor platform for OpenRouteService Travel Time."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OpenRouteServiceConfigEntry
from .coordinator import OpenRouteServiceCoordinator
from .entity import route_device_info

PARALLEL_UPDATES = 0

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="duration",
        translation_key="duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="distance",
        translation_key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
)


def duration_minutes(duration_seconds: float) -> float:
    """Convert provider seconds to Home Assistant native minutes."""
    return duration_seconds / 60.0


def distance_kilometres(distance_metres: float) -> float:
    """Convert provider metres to Home Assistant native kilometres."""
    return distance_metres / 1000.0


class OpenRouteServiceSensor(
    CoordinatorEntity[OpenRouteServiceCoordinator], SensorEntity
):
    """One value from a configured route."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenRouteServiceCoordinator,
        entry: OpenRouteServiceConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise a route sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the logical route device."""
        return route_device_info(
            self._entry.entry_id,
            str(self._entry.data[CONF_NAME]),
        )

    @property
    def native_value(self) -> float | None:
        """Return the current duration or distance when route data is available."""
        if not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        if self.entity_description.key == "duration":
            return duration_minutes(data.duration_seconds)
        return distance_kilometres(data.distance_metres)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenRouteServiceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up route sensors."""
    async_add_entities(
        OpenRouteServiceSensor(entry.runtime_data.coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )
