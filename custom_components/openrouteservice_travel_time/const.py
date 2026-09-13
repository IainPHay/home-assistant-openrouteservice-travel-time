"""Constants for OpenRouteService Travel Time."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN = "openrouteservice_travel_time"
NAME = "OpenRouteService Travel Time"
VERSION = "0.1.0-alpha.2"

API_BASE_URL = "https://api.heigit.org/openrouteservice/v2"
DEFAULT_PROFILE = "foot-walking"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
REQUEST_TIMEOUT_SECONDS = 20

CONF_ORIGIN = "origin"
CONF_DESTINATION = "destination"
CONF_PROFILE = "profile"

CONF_ORIGIN_TYPE = "origin_type"
CONF_DESTINATION_TYPE = "destination_type"
CONF_ORIGIN_LOCATION = "origin_location"
CONF_DESTINATION_LOCATION = "destination_location"
CONF_ORIGIN_ENTITY = "origin_entity"
CONF_DESTINATION_ENTITY = "destination_entity"

CONF_ENDPOINT_TYPE = "type"
CONF_ENDPOINT_ENTITY_ID = "entity_id"
ENDPOINT_FIXED: Final = "fixed"
ENDPOINT_ENTITY: Final = "entity"
LOCATION_ENTITY_DOMAINS: Final = ("person", "device_tracker")

PLATFORMS = [Platform.SENSOR]
