# Development and quality

## Engineering standard

This repository follows the same general engineering discipline used by BODS Bus Tracker while keeping the runtime architecture independent.

The Home Assistant Integration Quality Scale is treated as a design checklist. The source of truth for project progress is:

`custom_components/openrouteservice_travel_time/quality_scale.yaml`

A rule is marked `done` only when the implementation and supporting tests/documentation genuinely satisfy it. Exemptions include a reason. Incomplete rules remain `todo`.

## Current custom-integration localisation rule

Current Home Assistant developer documentation states that custom integrations should ship complete translations in `translations/<language>.json` and should not rely on Core's build-time `strings.json` mechanism.

This repository therefore uses:

`custom_components/openrouteservice_travel_time/translations/en.json`

and intentionally does not add `strings.json`.

## Validation gates

GitHub Actions runs:

1. HACS validation;
2. Hassfest;
3. manifest/runtime version synchronisation;
4. Home Assistant-native pytest with a 95% coverage floor;
5. strict mypy.

The coverage floor is a minimum, not a target to game. Config flow branches, provider error paths, lifecycle handling and privacy/redaction behaviour require direct tests.

## Test policy

Committed tests use synthetic coordinates and mocked HTTP.

Do not commit:

- real API keys;
- household coordinates;
- captured responses containing secrets/personal location;
- tests that rely on the live hosted API.

Real provider/Home Assistant validation is a separate pre-release step.

## Development sequence

1. Repository/quality scaffold.
2. Small async openrouteservice API client.
3. API-key validation.
4. Fixed-coordinate route config.
5. `foot-walking` coordinator.
6. Duration and Distance sensors.
7. Dynamic `person` / `device_tracker` resolution.
8. reconfigure and reauthentication flows.
9. diagnostics/privacy.
10. real HACS/Home Assistant validation.
11. only then broaden route profiles.

## Release discipline

For every release:

- keep `manifest.json` and `const.py` versions identical;
- update `CHANGELOG.md`;
- keep all CI gates green;
- document any new setting/entity;
- review diagnostics for secrets/location exposure;
- validate upgrade/reload behaviour in Home Assistant.
