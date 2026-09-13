# OpenRouteService Travel Time for Home Assistant

[![Version](https://img.shields.io/badge/version-0.1.0--alpha.1-blue.svg)](CHANGELOG.md)
[![HACS](https://img.shields.io/badge/HACS-custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Validate](https://github.com/IainPHay/home-assistant-openrouteservice-travel-time/actions/workflows/validate.yml/badge.svg)](https://github.com/IainPHay/home-assistant-openrouteservice-travel-time/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A modern standalone Home Assistant custom integration for [openrouteservice](https://openrouteservice.org/) route duration and distance.

The integration is designed for normal Home Assistant use: commute times, walking or cycling routes, station travel times, dashboards and automations. BODS Bus Tracker can consume its Duration sensor, but **BODS is only one downstream consumer** and there is no runtime dependency between the projects.

> **Development status:** pre-release. The repository scaffold is in place, but the first functional routing vertical slice is still being implemented.

## Planned first beta

The first beta deliberately starts small:

- Home Assistant UI configuration;
- one route per config entry;
- API key stored in the config entry;
- fixed coordinates or Home Assistant `person` / `device_tracker` locations;
- `foot-walking` routing first;
- **Duration** sensor using seconds natively;
- **Distance** sensor using a standard Home Assistant distance unit;
- approximately five-minute polling;
- normal Home Assistant manual entity refresh;
- reconfiguration and reauthentication;
- clean unload;
- translated UI, errors and entity names;
- privacy-safe diagnostics.

Cycling, driving and other routing profiles will follow only after walking has been validated end-to-end.

## Architecture

OpenRouteService Travel Time owns:

- openrouteservice API credentials;
- route calculation;
- origin and destination resolution;
- route profile;
- provider polling;
- provider-specific error handling.

Other integrations consume ordinary Home Assistant entities. They do not receive the API key or precise moving-person coordinates.

The hosted API implementation targets:

`https://api.heigit.org/openrouteservice/v2/`

The deprecated `api.openrouteservice.org` host will not be used.

See [Architecture](docs/ARCHITECTURE.md) for the project contract.

## Quality target

This project is engineered against the current Home Assistant Integration Quality Scale from the beginning.

The target is:

- Bronze aligned;
- Silver aligned;
- Gold aligned;
- applicable Platinum engineering practices, especially fully asynchronous network I/O, Home Assistant's shared web session and strict typing.

Because this is a third-party custom integration, the repository does **not** claim an official Home Assistant Core quality tier.

The living rule-by-rule ledger is [`quality_scale.yaml`](custom_components/openrouteservice_travel_time/quality_scale.yaml). CI is intended to enforce the same engineering style as BODS Bus Tracker:

- HACS validation;
- Hassfest;
- Home Assistant-native pytest tests;
- at least 95% integration coverage;
- strict mypy;
- manifest/runtime version synchronisation.

See [Development and quality](docs/DEVELOPMENT.md).

## Requirements

For the first beta the expected requirements are:

- Home Assistant 2026.8 or newer;
- HACS for HACS installation, or manual access to `custom_components`;
- a free openrouteservice API key.

## Get an openrouteservice API key

1. Create an account through [openrouteservice](https://openrouteservice.org/).
2. Create/copy an API key from the provider dashboard.
3. Keep the key private. The integration will store it in the Home Assistant config entry and redact it from diagnostics.

Do not publish an API key in GitHub issues or diagnostic attachments.

## Installation with HACS

The repository is structured as a HACS custom integration repository.

Until the first beta is released, installation is intended for development/testing only.

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add:
   `https://github.com/IainPHay/home-assistant-openrouteservice-travel-time`
4. Select category **Integration**.
5. Install **OpenRouteService Travel Time** when a release is available.
6. Restart Home Assistant.

You can open the repository in HACS with:

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=IainPHay&repository=home-assistant-openrouteservice-travel-time&category=integration)

## Manual installation

Once a functional beta is available:

1. Download the repository/release.
2. Copy `custom_components/openrouteservice_travel_time/` to `/config/custom_components/openrouteservice_travel_time/`.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **OpenRouteService Travel Time**.

## Configuration

The intended first-beta route configuration is:

| Setting | Purpose |
| --- | --- |
| API key | Authenticates requests to the hosted openrouteservice API. |
| Route name | Human-readable name for the configured route/device. |
| Origin | Fixed coordinates or a Home Assistant entity exposing latitude/longitude. |
| Destination | Fixed coordinates or a Home Assistant entity exposing latitude/longitude. |
| Profile | Initially `foot-walking`. |
| Poll interval | Conservative provider refresh interval, initially about five minutes. |

Dynamic entities are resolved at update time. The integration will not silently substitute Home Assistant's home coordinates when configured coordinates are missing.

## Entities

The initial route device will expose:

| Entity | Home Assistant semantics |
| --- | --- |
| **Duration** | `SensorDeviceClass.DURATION`, native seconds. |
| **Distance** | `SensorDeviceClass.DISTANCE`, standard native distance unit. |

Values must be numeric, finite and non-negative. If a trustworthy route cannot be calculated, the relevant route entities become unavailable rather than exposing a guessed value.

## Data updates

The first release will use a `DataUpdateCoordinator` with a conservative default interval of approximately five minutes.

A normal Home Assistant `homeassistant.update_entity` refresh remains supported. Every provider refresh can consume openrouteservice quota, so the integration will not poll at high frequency merely because a downstream consumer updates more often.

## Error and recovery behaviour

The integration will distinguish provider failures rather than collapsing them into a generic authentication error:

- confirmed invalid credentials → Home Assistant reauthentication;
- rate limiting → transient update failure/backoff, without invalidating credentials;
- timeout/network/server failure → transient coordinator failure;
- missing or invalid dynamic coordinates → route unavailable;
- no route found → unavailable, without straight-line or estimated substitution;
- HTTP 403 → inspect provider response before deciding whether credentials are invalid.

Normal transient recovery must not require reconfiguration.

## Use cases

Typical uses include:

- walking time from a moving person to a bus or rail stop;
- commute duration from home to work;
- travel time to an appointment;
- distance and duration cards on a Home Assistant dashboard;
- automations that react to a route duration threshold;
- provider-neutral routed walking input for BODS Bus Tracker.

## Example automation

Once the Duration sensor exists, it can be consumed like any other Home Assistant duration sensor. For example, an automation can react when a route becomes short enough to leave for a connection.

The repository will add a ready-to-import generic example/blueprint once entity behaviour has been validated in a real Home Assistant instance.

## Privacy and data handling

A directions request necessarily sends the configured origin and destination coordinates to openrouteservice.

The integration will minimise secondary exposure:

- API keys remain in the config entry;
- API keys are redacted from diagnostics;
- precise moving-person coordinates are not copied into Recorder attributes;
- precise moving-person coordinates are excluded from downloadable diagnostics unless a future feature has a compelling, documented reason;
- no project analytics or telemetry are planned.

## Known limitations

For the first beta:

- one route per config entry;
- walking is the only supported profile initially;
- route calculation depends on the hosted openrouteservice service and account quota;
- dynamic Home Assistant entities must expose usable latitude/longitude;
- the integration does not infer or substitute a route when the provider cannot calculate one;
- no geocoding/address search is planned for the first beta.

## Troubleshooting

The integration is not yet ready for normal troubleshooting. During development:

- check the GitHub Actions validation result;
- include the Home Assistant version and integration version when reporting a problem;
- include downloaded integration diagnostics once diagnostics are implemented;
- never include an API key or unredacted precise personal coordinates in an issue.

## Removing the integration

Once the config flow is implemented:

1. Open **Settings → Devices & services → OpenRouteService Travel Time**.
2. Remove each route config entry you no longer want.
3. If installed through HACS, remove **OpenRouteService Travel Time** from HACS after the Home Assistant entries have been removed.

Deleting a Home Assistant config entry does not revoke the API key at openrouteservice.

## Attribution

This project integrates with the [openrouteservice](https://openrouteservice.org/) API. Route data and service availability remain subject to the provider's terms and upstream OpenStreetMap-derived data.

This is an independent community integration and is not affiliated with or endorsed by Home Assistant, HACS, HeiGIT or openrouteservice.

## Licence

Released under the [MIT License](LICENSE).
