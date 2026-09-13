# Contributing

Thanks for helping improve OpenRouteService Travel Time.

## Project boundary

Keep this integration standalone.

It owns openrouteservice credentials, routing, origin/destination resolution and provider-specific behaviour. Do not add BODS-specific runtime code. BODS Bus Tracker is only a downstream consumer of the normal Home Assistant Duration sensor.

## Privacy

Never include:

- openrouteservice API keys;
- unredacted secrets;
- precise moving-person coordinates from a real household;
- diagnostics containing location data that have not been reviewed/redacted.

Use synthetic coordinates in committed tests.

## Pull requests

Keep changes focused and preserve the staged development plan.

Before submitting code changes:

1. ensure the integration remains fully typed;
2. run the Home Assistant-native test suite;
3. maintain at least 95% coverage once functional modules are introduced;
4. keep `manifest.json` and `const.py` versions aligned;
5. update `CHANGELOG.md` for user-visible changes;
6. update `quality_scale.yaml` when a rule changes state;
7. keep translations complete;
8. preserve the explicit error classification between invalid authentication, forbidden access, rate limiting, transient network/server errors and no-route responses.

The normal CI gates are HACS, Hassfest, version sync, pytest/coverage and strict mypy.
