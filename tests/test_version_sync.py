"""Release version consistency tests."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.openrouteservice_travel_time.const import (
    API_BASE_URL,
    DEFAULT_PROFILE,
    VERSION,
)


def test_manifest_and_runtime_versions_match() -> None:
    """The manifest and runtime version constants must match."""
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root
            / "custom_components"
            / "openrouteservice_travel_time"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert VERSION == manifest["version"]


def test_provider_baseline_constants() -> None:
    """The bootstrap must target the current provider host and walking profile."""
    assert API_BASE_URL == "https://api.heigit.org/openrouteservice/v2"
    assert DEFAULT_PROFILE == "foot-walking"
