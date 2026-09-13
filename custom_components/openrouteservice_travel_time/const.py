"""Constants for OpenRouteService Travel Time."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "openrouteservice_travel_time"
NAME = "OpenRouteService Travel Time"
VERSION = "0.1.0-alpha.1"

API_BASE_URL = "https://api.heigit.org/openrouteservice/v2"
DEFAULT_PROFILE = "foot-walking"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
