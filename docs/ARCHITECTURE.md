# Architecture

## Purpose

OpenRouteService Travel Time is a standalone Home Assistant custom integration. It converts an openrouteservice route calculation into normal Home Assistant entities without embedding downstream application logic.

## Repository and domain

- Repository: `IainPHay/home-assistant-openrouteservice-travel-time`
- Home Assistant domain: `openrouteservice_travel_time`
- Licence: MIT

The legacy archived custom integration used the domain `open_route_service`. This project intentionally uses a different domain and is a new implementation rather than a silent takeover.

## Provider boundary

This integration owns:

- API credentials;
- openrouteservice HTTP requests;
- origin and destination resolution;
- routing profile;
- provider polling;
- provider error classification.

Consumers receive normal Home Assistant entity states. They do not own provider credentials or API behaviour.

BODS Bus Tracker is one validation consumer. It remains provider-neutral and reads only a standard duration sensor.

## API baseline

Hosted API base:

`https://api.heigit.org/openrouteservice/v2`

Initial directions request:

`POST /directions/foot-walking`

Authentication uses the `Authorization` header.

Coordinates use `[longitude, latitude]` order.

For the JSON directions response, the route summary provides distance in metres and duration in seconds.

The HTTP layer is deliberately small and uses Home Assistant's shared async aiohttp session instead of a separate third-party Python SDK.

## v0.1 route model

The first release uses one route per Home Assistant config entry.

A route contains:

- API key;
- human-readable route name;
- origin endpoint;
- destination endpoint;
- routing profile.

Polling is currently fixed at five minutes.

### Endpoint representation

An endpoint is either:

1. **fixed** — explicit latitude/longitude selected in the UI; or
2. **entity** — a Home Assistant `person` or `device_tracker` entity ID.

Fixed endpoints are stored in canonical form:

```json
{
  "type": "fixed",
  "latitude": 55.1,
  "longitude": -1.6
}
```

Dynamic endpoints are stored as references, not coordinates:

```json
{
  "type": "entity",
  "entity_id": "person.example"
}
```

The alpha.2 parser also accepts the alpha.1 direct latitude/longitude mapping so development installs are not unnecessarily broken.

### Dynamic endpoint resolution

For an entity endpoint, the coordinator reads the entity immediately before each provider request.

The state is trusted only when:

- the entity exists;
- its state is neither `unknown` nor `unavailable`;
- it exposes numeric latitude and longitude;
- both coordinates are finite and within geographic ranges.

No Home Assistant home-coordinate fallback is permitted.

No last-known route is substituted when current location state is untrustworthy.

## Stable route identity

Duplicate detection must not use the current coordinates of a moving person.

The config-entry unique ID is therefore derived from:

- route profile;
- fixed endpoint coordinates for fixed endpoints;
- entity IDs for dynamic endpoints.

This keeps identity stable while the person/device tracker moves.

## Runtime design

1. Config flow collects route name and endpoint types.
2. A second config-flow step collects fixed locations or entity references.
3. The current endpoint coordinates and API access are validated before the entry is created.
4. Typed `ConfigEntry.runtime_data` owns the API client and coordinator.
5. `DataUpdateCoordinator` resolves current coordinates immediately before each provider request.
6. Duration and Distance entities read coordinator data.
7. Reconfiguration can change endpoint types and references.
8. Confirmed credential rejection initiates Home Assistant reauthentication.
9. Clean unload delegates to Home Assistant platform lifecycle handling.

## Entity contract

### Duration

- sensor device class: duration;
- native unit: seconds;
- numeric, finite, non-negative;
- unavailable when the latest coordinator update is not trustworthy.

### Distance

- sensor device class: distance;
- native unit: metres;
- numeric, finite, non-negative;
- unavailable when the latest coordinator update is not trustworthy.

Both entities belong to one logical service device representing the configured route.

## Provider error policy

Errors remain deliberately distinct:

- confirmed HTTP 401 or unambiguous invalid-key response → reauthentication;
- ambiguous HTTP 403 → access-forbidden/transient failure, not forced reauthentication;
- HTTP 429 → transient rate-limit failure;
- timeout/network failure → transient update failure;
- provider/server/malformed-response failure → transient update failure;
- invalid or missing dynamic coordinates → route unavailable;
- no route → route unavailable.

Non-JSON provider/proxy error bodies are tolerated for HTTP-status classification. A successful response must still contain valid expected JSON.

One failed update must not crash Home Assistant.

## Privacy

Precise coordinates are operational inputs, not diagnostic data.

Dynamic coordinates are resolved in memory and are not copied into:

- config-entry data;
- entity attributes;
- routine logs;
- downloadable diagnostics;
- Recorder history.

Fixed coordinates and the API key are redacted from diagnostics.

## Expansion rule

Walking remains the first vertical slice. Cycling/driving/hiking/wheelchair profiles should be added only after the walking implementation has been installed and validated end-to-end in a real Home Assistant instance with quality gates green.
