# Changelog

All notable changes to OpenRouteService Travel Time are documented here.

The project uses semantic versioning for integration releases.

## 0.1.0-alpha.4 — development

### Fixed

- Resolve `person` endpoints that are inside a Home Assistant zone even when the `person` entity itself does not expose latitude/longitude attributes.
- Fall back to the person's currently selected `source` device tracker when direct person coordinates and zone coordinates are unavailable.
- Preserve the rule that no location is guessed: if person, zone and source tracker cannot provide trustworthy coordinates, the route remains unavailable.
- Added Home Assistant-native regression tests covering direct person coordinates, zone resolution, zone friendly-name matching, source-tracker fallback, direct device-tracker resolution and unavailable-location handling.

## 0.1.0-alpha.3 — development

### Fixed

- Fixed a real Home Assistant config-flow rendering failure where a required fixed destination `LocationSelector` had no initial value, causing the endpoint form to appear blank in the frontend before the selector could render.
- Added a regression test requiring both fixed-location selectors to supply valid Home Assistant location defaults.

## 0.1.0-alpha.2 — development

### Added

- Dynamic route endpoints using Home Assistant `person` and `device_tracker` entities.
- Two-step route setup that explicitly chooses fixed or dynamic endpoints.
- Runtime endpoint resolution on every coordinator update.
- Stable duplicate-route identity based on entity IDs rather than moving coordinates.
- Endpoint availability validation during setup and reconfiguration.
- More defensive provider error handling for non-JSON HTTP errors.

### Changed

- Fixed endpoints now use an explicit canonical persisted representation while remaining backward-compatible with alpha.1 fixed-coordinate entries.
- README, architecture documentation and quality-scale tracking updated to match the functional implementation.

## 0.1.0-alpha.1 — development

### Added

- Initial standalone HACS repository scaffold.
- Home Assistant manifest and domain `openrouteservice_travel_time`.
- HACS metadata and validation workflow.
- Home Assistant Integration Quality Scale tracking.
- Strict typing and Home Assistant-native test scaffolding.
- English translation and entity-icon scaffolding.
- Architecture, development, privacy and installation documentation.
- First fixed-coordinate `foot-walking` route vertical slice.
- Duration and Distance sensors.
- Reauthentication, reconfiguration and privacy-safe diagnostics.
