# OpenRouteService Travel Time for Home Assistant

[![Version](https://img.shields.io/badge/version-0.1.0--alpha.6-blue.svg)](CHANGELOG.md)
[![HACS](https://img.shields.io/badge/HACS-custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Validate](https://github.com/IainPHay/home-assistant-openrouteservice-travel-time/actions/workflows/validate.yml/badge.svg)](https://github.com/IainPHay/home-assistant-openrouteservice-travel-time/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A standalone Home Assistant custom integration for [openrouteservice](https://openrouteservice.org/) route duration and distance.

It is designed for ordinary Home Assistant use: walking-time sensors, commute routes, station/stop travel times, dashboards and automations. BODS Bus Tracker can consume its Duration sensor, but **BODS is only one downstream consumer** and there is no runtime dependency between the projects.

> **Development status:** pre-release. The walking route implementation, dynamic Home Assistant location endpoints, quota-aware polling/caching and Home Assistant-native sensor presentation have been validated in a real Home Assistant/HACS installation.

## Current alpha

The current `0.1.0-alpha.6` implementation provides:

- Home Assistant UI-only configuration;
- one route per config entry;
- API key stored in the config entry;
- fixed map locations;
- dynamic `person` and `device_tracker` endpoints;
- `person` resolution through direct coordinates, current zone, then source device tracker;
- `foot-walking` routing;
- **Duration** sensor in minutes with zero suggested decimal places;
- **Distance** sensor in kilometres with one suggested decimal place;
- five-minute coordinator updates with a hard five-minute minimum between provider calls per route;
- coordinate-aware caching with a 25 m movement threshold and six-hour TTL;
- normal Home Assistant manual entity refresh without bypassing provider throttling;
- reconfiguration and reauthentication;
- clean unload;
- translated UI, errors, selector options and entity names;
- privacy-safe diagnostics;
- HACS/Hassfest validation, strict typing and Home Assistant-native tests.

Cycling, driving and other routing profiles will be added only after the walking implementation is fully proven end-to-end.

## Architecture

OpenRouteService Travel Time owns:

- openrouteservice API credentials;
- route calculation;
- origin and destination resolution;
- route profile;
- provider polling and quota protection;
- provider-specific error handling.

Other integrations consume ordinary Home Assistant entities. They do not receive the API key or precise moving-person coordinates.

The hosted API implementation targets:

`https://api.heigit.org/openrouteservice/v2/`

The deprecated `api.openrouteservice.org` host is not used.

See [Architecture](docs/ARCHITECTURE.md) for the project contract and [Provider quota](docs/PROVIDER_QUOTA.md) for request ceilings and cache behaviour.

## Quality target

This project is engineered against the current Home Assistant Integration Quality Scale from the beginning.

The target is:

- Bronze aligned;
- Silver aligned;
- Gold aligned;
- applicable Platinum engineering practices, especially fully asynchronous network I/O, Home Assistant's shared web session and strict typing.

Because this is a third-party custom integration, the repository does **not** claim an official Home Assistant Core quality tier.

The living rule-by-rule ledger is [`quality_scale.yaml`](custom_components/openrouteservice_travel_time/quality_scale.yaml). CI follows the same engineering approach used for BODS Bus Tracker:

- HACS validation;
- Hassfest;
- Home Assistant-native pytest tests;
- at least 95% integration coverage;
- strict mypy;
- manifest/runtime version synchronisation.

See [Development and quality](docs/DEVELOPMENT.md).

## Requirements

The current alpha expects:

- Home Assistant 2026.8 or newer;
- HACS for HACS installation, or manual access to `custom_components`;
- a free openrouteservice API key.

## Get an openrouteservice API key

1. Create an account through [openrouteservice](https://openrouteservice.org/).
2. Create/copy an API key from the provider dashboard.
3. Keep the key private. The integration stores it in the Home Assistant config entry and redacts it from diagnostics.

Do not publish an API key in GitHub issues or diagnostic attachments.

## Installation with HACS

The repository is structured as a HACS custom integration repository.

Until the first beta is released, installation is intended for development/testing.

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

1. Download the repository/release.
2. Copy `custom_components/openrouteservice_travel_time/` to `/config/custom_components/openrouteservice_travel_time/`.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **OpenRouteService Travel Time**.

## Configuration

Setup is deliberately explicit.

### Step 1 — route identity and endpoint types

Enter:

- the openrouteservice API key;
- a route name;
- whether the **origin** is a fixed location or a `person` / `device_tracker`;
- whether the **destination** is a fixed location or a `person` / `device_tracker`.

### Step 2 — route endpoints

For each fixed endpoint, choose a map location.

For each dynamic endpoint, select a Home Assistant `person` or `device_tracker` entity. The integration validates that a trustworthy location can currently be resolved.

For `person` entities, location resolution is Home Assistant-native and deliberately conservative:

1. direct person latitude/longitude, if available;
2. coordinates of the person's current Home Assistant zone;
3. coordinates of the person's selected source `device_tracker`;
4. otherwise unavailable.

The API key and route are tested before Home Assistant creates the config entry.

### Runtime behaviour of dynamic endpoints

Dynamic endpoint state is resolved again on every coordinator update. Coordinates are not copied into the config entry.

If the configured endpoint cannot provide a trustworthy location, the route becomes unavailable. The integration does **not** silently substitute Home Assistant's home coordinates or an old route.

This follows the project rule that behaviour must not be automated from untrusted state.

## Entities

Each route is represented as one logical service device with two primary entities:

| Entity | Home Assistant semantics |
| --- | --- |
| **Duration** | `SensorDeviceClass.DURATION`, native unit minutes, zero suggested decimal places. |
| **Distance** | `SensorDeviceClass.DISTANCE`, native unit kilometres, one suggested decimal place. |

OpenRouteService provider data remains stored internally as seconds and metres; conversion happens only at the Home Assistant sensor boundary.

Values are numeric, finite and non-negative. If a trustworthy route cannot be calculated, the coordinator update fails and the route entities become unavailable rather than exposing a guessed value.

## Data updates and quota protection

The integration uses a `DataUpdateCoordinator` with a five-minute update interval, but coordinator updates are intentionally separated from provider request frequency.

Each configured route has a **hard minimum of five minutes between OpenRouteService requests**. Repeated manual refreshes or downstream consumers cannot bypass that ceiling. This gives a theoretical maximum of **288 provider requests per day per route**.

To reduce provider usage further:

- endpoint coordinates are resolved on every coordinator update;
- a cached route is reused while both endpoints have moved less than 25 m;
- the cached route is forcibly revalidated after six hours;
- fixed/stationary routes therefore usually need only about four provider calls per day.

For moving-person use cases, the person's/device tracker's current location is resolved at update time, not setup time.

See [Provider quota](docs/PROVIDER_QUOTA.md) for the full policy.

## Error and recovery behaviour

Failures are deliberately classified:

- confirmed invalid credentials → Home Assistant reauthentication;
- HTTP 429 → transient update failure; credentials remain valid;
- timeout/network/server failure → transient update failure;
- missing or invalid dynamic location → route unavailable;
- no route found → unavailable, without straight-line or estimated substitution;
- HTTP 403 → provider response is inspected; an ambiguous 403 does not automatically invalidate the API key;
- malformed provider response → unavailable rather than returning guessed values.

Normal transient recovery does not require reconfiguration.

## Use cases

Typical uses include:

- walking time from a moving person to a bus or rail stop;
- walking time from a fixed home location to a destination;
- commute duration;
- route distance/duration cards on a dashboard;
- automations based on a standard duration sensor;
- provider-neutral routed walking input for BODS Bus Tracker.

### BODS Bus Tracker and multiple people

A common configuration is:

- **Origin:** `person.<name>` or the user's phone `device_tracker`;
- **Destination:** fixed coordinates of the bus stop;
- **Profile:** `foot-walking`.

For a two-person household, create one OpenRouteService route per person, for example:

- `person.iain` → target bus stop;
- `person.abbi` → target bus stop.

Each route has its own request ceiling and cache. BODS can then evolve to accept separate routed walking-time sensors and choose the appropriate person's route by context, while remaining independent of OpenRouteService credentials and API behaviour.

### Dashboard example

Replace the entity IDs with the two entities created for your route:

```yaml
type: entities
title: Route to bus stop
entities:
  - entity: sensor.route_to_bus_stop_duration
  - entity: sensor.route_to_bus_stop_distance
```

## Privacy and data handling

A directions request necessarily sends the resolved origin and destination coordinates to openrouteservice.

The integration minimises secondary exposure:

- API keys remain in the config entry;
- API keys are redacted from diagnostics;
- fixed endpoint coordinates are redacted from diagnostics;
- dynamic entity coordinates are resolved in memory at update time;
- precise moving-person coordinates are not stored in entity attributes;
- precise moving-person coordinates are not written into downloadable diagnostics;
- no project analytics or telemetry are planned.

Dynamic entity IDs are used only to retrieve state from the local Home Assistant instance.

## Troubleshooting

### Route entities are unavailable

Check the configured `person` / `device_tracker` endpoint first. A `person` may resolve from direct coordinates, its current Home Assistant zone, or its source tracker. If none is trustworthy, the route is intentionally unavailable.

### API key rejected

A confirmed authentication rejection starts Home Assistant reauthentication. Enter a replacement openrouteservice API key there; the route configuration is retained.

### HTTP 403 / access forbidden

A 403 is not automatically treated as a bad key because provider access/policy failures can also use that status. Check the Home Assistant log and provider account/service status before replacing credentials.

### Rate limiting

HTTP 429 is treated as a transient provider failure. The integration already enforces a five-minute per-route provider-call minimum and movement-aware caching; allow the normal coordinator to recover rather than repeatedly forcing updates.

### No route

The integration does not substitute straight-line distance or an estimated duration when openrouteservice cannot calculate a route.

### Reporting an issue

Include:

- Home Assistant version;
- integration version;
- downloaded integration diagnostics;
- relevant Home Assistant log messages.

Never include an API key or unredacted precise personal coordinates.

## Known limitations

For the current alpha:

- one route per config entry;
- walking is the only supported routing profile;
- coordinator interval and provider minimum interval are currently fixed at five minutes;
- route calculation depends on the hosted openrouteservice service and account quota;
- dynamic endpoints are limited to `person` and `device_tracker`;
- no geocoding/address search is provided;
- the integration does not infer or substitute a route when provider/location state is not trustworthy.

## Reconfiguration

Open **Settings → Devices & services → OpenRouteService Travel Time**, choose the route and use **Reconfigure**.

You can change:

- route name;
- origin type;
- origin location/entity;
- destination type;
- destination location/entity.

The existing API key is retained.

## Removing the integration

1. Open **Settings → Devices & services → OpenRouteService Travel Time**.
2. Remove each route config entry you no longer want.
3. If installed through HACS, remove **OpenRouteService Travel Time** from HACS after the Home Assistant entries have been removed.

Deleting a Home Assistant config entry does not revoke the API key at openrouteservice.

## Attribution

This project integrates with the [openrouteservice](https://openrouteservice.org/) API. Route data and service availability remain subject to the provider's terms and upstream OpenStreetMap-derived data.

This is an independent community integration and is not affiliated with or endorsed by Home Assistant, HACS, HeiGIT or openrouteservice.

## Licence

Released under the [MIT License](LICENSE).
