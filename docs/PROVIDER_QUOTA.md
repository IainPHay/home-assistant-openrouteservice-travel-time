# Provider quota and polling

OpenRouteService Travel Time is designed so Home Assistant refresh activity cannot accidentally consume provider quota without bound.

## Per-route hard limit

Each configured route has a hard minimum interval of five minutes between OpenRouteService provider requests.

Even if a dashboard, automation, BODS Bus Tracker, or `homeassistant.update_entity` requests updates more often, the integration will reuse the most recent route result until the hard interval has elapsed.

The theoretical maximum for one route is therefore:

`24 × 60 ÷ 5 = 288 requests/day`

For two independently configured person-to-stop routes the theoretical ceiling is 576 requests/day, and so on.

This is deliberately a ceiling rather than an expected request rate.

## Why normal use is lower

After the five-minute hard interval has elapsed, the integration compares the current resolved origin and destination with the coordinates used for the last provider request.

If both endpoints have moved less than 25 metres, the cached route is reused. This suppresses calls caused by GPS jitter and tiny movements that are unlikely to change a walking route meaningfully.

A cached route is never kept forever: it expires after six hours. A fixed-to-fixed or otherwise stationary route will therefore normally make about four provider requests per day.

Examples:

| Route behaviour | Typical provider behaviour |
| --- | --- |
| Fixed → fixed | Initial request, then approximately one refresh every six hours |
| Person at home/inside a zone | Zone coordinates stay stable; cached route is reused until TTL expiry |
| Person walking | At most one provider request every five minutes, and only after material movement |
| Repeated manual refreshes | Cannot bypass the five-minute hard provider-call limit |
| GPS jitter below 25 m | Cached route is reused |

## Provider account quota

OpenRouteService plan quotas and policies are controlled by OpenRouteService and may change independently of this integration. Check the current quota shown in the provider account/dashboard before creating large numbers of routes.

The integration's hard ceiling makes capacity planning straightforward:

`maximum daily requests = configured routes × 288`

The actual number should normally be much lower because of movement-aware caching and the six-hour stationary-route TTL.

## Multi-person BODS design

The quota policy intentionally applies per OpenRouteService route/config entry rather than inside BODS Bus Tracker.

That supports a clean two-person household design such as:

- **Iain walking route:** `person.iain` → selected bus stop;
- **Abbi walking route:** `person.abbi` → selected bus stop.

BODS can consume the resulting duration entities without knowing OpenRouteService credentials, coordinates, cache policy, or provider error handling.

A future BODS enhancement can therefore accept separate routed walking-time sensors for two people and select the appropriate one according to person/context. This is more flexible than embedding one person's route logic directly in BODS, while retaining independent quota protection for each route.

## Failure behaviour

Quota protection never substitutes guessed route data when the current endpoint state is untrustworthy. If a selected dynamic endpoint cannot be resolved to valid coordinates, the route becomes unavailable rather than silently using a stale person's location.

HTTP 429 remains a transient provider failure. Users should allow the normal coordinator cycle to recover rather than repeatedly forcing updates.
