"""Shared entity helpers for OpenRouteService Travel Time."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN, VERSION


def route_device_info(entry_id: str, route_name: str) -> DeviceInfo:
    """Return consistent metadata for one logical route device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=route_name,
        manufacturer="openrouteservice / HeiGIT",
        model="Route",
        sw_version=VERSION,
        configuration_url="https://openrouteservice.org/",
        entry_type=DeviceEntryType.SERVICE,
    )
