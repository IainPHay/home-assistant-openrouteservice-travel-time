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
- provider polling and quota protection;
- provider error classification.

Consumers receive normal Home Assistant entity states. They do not own provider credentials or API behaviour.

BODS Bus Tracker is one validation consumer. It remains provider-neutral and reads only standard duration sensors.

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

The coordinator checks route state on a five-minute interval, but coordinator updates and provider requests are deliberately separated. Provider calls are quota-protected and may be skipped when a recent route result is still valid.

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

The parser also accepts the alpha.1 direct latitude/longitude mapping so development installs are not unnecessarily broken.

### Dynamic endpoint resolution

For an entity endpoint, current coordinates are resolved immediately before each coordinator update.

For a `person` endpoint the trusted resolution order is:

1. direct latitude/longitude attributes on the person;
2. coordinates of an explicitly reported containing Home Assistant zone;
3. the person's currently selected source `device_tracker`;
4. unavailable if none of the above provide trustworthy coordinates.

For a direct `device_tracker` endpoint, numeric latitude/longitude attributes are required.

The state is trusted only when the entity exists, is not `unknown`/`unavailable`, and the resolved coordinates are finite and geographically valid.

No guessed Home Assistant home-coordinate fallback is permitted. No last-known route is substituted when the current location state itself is untrustworthy.

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
5. `DataUpdateCoordinator` resolves current coordinates on each coordinator update.
6. Quota policy decides whether a provider request is needed or a cached route can be reused.
7. Duration and Distance entities read coordinator data.
8. Reconfiguration can change endpoint types and references.
9. Confirmed credential rejection initiates Home Assistant reauthentication.
10. Clean unload delegates to Home Assistant platform lifecycle handling.

## Provider quota and route-cache policy

The integration deliberately protects OpenRouteService quota per configured route.

### Hard request ceiling

A config entry cannot make provider requests more frequently than once every five minutes, even if Home Assistant or a downstream integration repeatedly forces entity refreshes.

The theoretical maximum is therefore:

`24 hours × 60 minutes ÷ 5 minutes = 288 provider requests/day/route`

This is a ceiling, not a target. Normal use should be substantially lower because the coordinator reuses cached routes when endpoint movement does not justify a recalculation.

### Movement threshold

After the hard five-minute interval has elapsed, a cached route remains valid while both endpoints have moved less than 25 metres from the coordinates used for the last provider request.

This avoids wasting quota on GPS jitter or tiny movements that are unlikely to change a walking route meaningfully.

### Cache TTL

Even when endpoints remain stationary, the cached route expires after six hours. A fresh provider request is then made so fixed/stationary routes are not cached indefinitely.

For a permanently fixed route this normally means about four provider requests per day rather than 288.

### Multi-person implications

Quota protection is per route/config entry. This makes it practical to configure separate routed walking sensors for different people, for example:

- `person.iain` → a bus stop;
- `person.abbi` → the same bus stop.

Each route has its own hard request ceiling and cache. BODS Bus Tracker can remain provider-neutral and may evolve to consume more than one routed walking-time sensor for a two-person household without either user having to share raw OpenRouteService logic or credentials with BODS.

Provider plan quotas can change, so users should still check the limits shown in their OpenRouteService account/dashboard when creating many routes.

See [Provider quota and polling](PROVIDER_QUOTA.md) for worked examples.

## Entity contract

### Duration

- sensor device class: duration;
- native unit: minutes;
- provider value is retained internally in seconds and converted at the entity boundary;
- suggested display precision: 0 decimal places;
- numeric, finite, non-negative;
- unavailable when the latest coordinator update is not trustworthy.

### Distance

- sensor device class: distance;
- native unit: metres;
- suggested display precision: 0 decimal places;
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
