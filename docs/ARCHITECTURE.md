# Architecture

## Purpose

OpenRouteService Travel Time is a standalone Home Assistant custom integration. It converts an openrouteservice route calculation into normal Home Assistant route entities without embedding downstream application logic.

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
- polling;
- provider error classification.

Consumers receive normal Home Assistant entity states. They do not own provider credentials or API behaviour.

BODS Bus Tracker is one validation consumer. It must remain provider-neutral and read only a standard duration sensor.

## API baseline

Hosted API base:

`https://api.heigit.org/openrouteservice/v2`

Initial directions request:

`POST /directions/foot-walking`

Authentication uses the `Authorization` header.

Coordinates use `[longitude, latitude]` order.

For the JSON directions response the route summary provides distance in metres and duration in seconds.

The HTTP layer should remain small and isolated so tests can mock it without a third-party Python SDK.

## v0.1 route model

The first release uses one route per Home Assistant config entry.

A route contains:

- API key;
- human-readable route name;
- origin;
- destination;
- routing profile;
- polling settings.

Origin/destination may be fixed coordinates or a Home Assistant entity with usable latitude/longitude. Dynamic entities are resolved at update time.

Home Assistant home coordinates are never used as an implicit fallback.

## Runtime design

The intended runtime pattern is:

1. config flow validates credentials and route input;
2. typed ConfigEntry runtime data owns the API client and coordinator;
3. DataUpdateCoordinator resolves current coordinates and performs one route request;
4. Duration and Distance entities read coordinator data;
5. reconfiguration updates route settings;
6. confirmed credential rejection initiates reauthentication;
7. unload releases platforms/runtime work cleanly.

The client uses Home Assistant's shared async aiohttp session.

## Entity contract

### Duration

- Sensor device class: duration;
- native unit: seconds;
- numeric, finite, non-negative;
- unavailable when no trustworthy route exists.

### Distance

- Sensor device class: distance;
- native unit: metres unless implementation evidence supports a better standard native choice;
- numeric, finite, non-negative;
- unavailable when no trustworthy route exists.

## Provider error policy

Errors are classified deliberately:

- confirmed invalid credentials → reauthentication;
- HTTP 429 → transient rate-limit failure/backoff;
- timeout/network/5xx → transient update failure;
- invalid/missing dynamic coordinates → route unavailable;
- no route → unavailable;
- HTTP 403 → inspect response; do not assume invalid credentials.

One failed route update must not crash Home Assistant.

## Privacy

Precise dynamic coordinates are operational inputs, not diagnostic data.

Do not copy them into:

- entity attributes;
- routine logs;
- downloadable diagnostics;
- Recorder history.

Diagnostics redact the API key.

## Expansion rule

Walking is the first vertical slice. Do not add cycling/driving/hiking/wheelchair profiles until walking works end-to-end in a real Home Assistant installation and the quality gates remain green.
