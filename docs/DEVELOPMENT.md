# Development and quality

## Engineering standard

This repository follows the same general engineering discipline used by BODS Bus Tracker while keeping the runtime architecture independent.

The Home Assistant Integration Quality Scale is treated as a design checklist. The source of truth for project progress is:

`custom_components/openrouteservice_travel_time/quality_scale.yaml`

A rule is marked `done` only when the implementation and supporting tests/documentation genuinely satisfy it. Exemptions include a reason. Incomplete rules remain `todo`.

## Current custom-integration localisation rule

Current Home Assistant custom integrations ship complete English UI content in:

`custom_components/openrouteservice_travel_time/translations/en.json`

The project intentionally does not add a Core-style `strings.json` file.

## Validation gates

GitHub Actions runs:

1. HACS validation;
2. Hassfest;
3. manifest/runtime version synchronisation;
4. Home Assistant-native pytest with a 95% coverage floor;
5. strict mypy.

Repository metadata required by HACS is also maintained: description, topics, licence and local brand asset.

The coverage floor is a minimum, not a target to game. Config-flow branches, provider error paths, lifecycle handling, endpoint trust rules and privacy/redaction behaviour receive direct tests.

## Test policy

Committed tests use synthetic coordinates and mocked provider HTTP.

Do not commit:

- real API keys;
- household coordinates;
- captured responses containing secrets/personal location;
- tests that rely on the live hosted API.

Dynamic-location tests use synthetic `person` and `device_tracker` states.

Real provider/Home Assistant validation is a separate pre-release gate.

## Development sequence

Completed in the current branch:

1. repository/quality scaffold;
2. small async openrouteservice API client;
3. API-key validation;
4. fixed-coordinate route configuration;
5. `foot-walking` coordinator;
6. Duration and Distance sensors;
7. dynamic `person` / `device_tracker` endpoint resolution;
8. reconfiguration and reauthentication;
9. privacy-safe diagnostics;
10. HACS/Hassfest/typing/test CI gates.

Next:

11. install the integration into a real Home Assistant test instance through HACS/custom repository;
12. validate fixed and moving-person walking routes against the live provider;
13. validate reload, restart, reauth and unavailable/recovery behaviour;
14. validate BODS Bus Tracker consumption of the Duration sensor;
15. only then broaden route profiles.

## Endpoint-state principle

The integration follows a strict rule:

> Do not automate behaviour until state is trusted.

For dynamic endpoints, missing, unavailable or coordinate-less entities produce an unavailable route. Do not add a hidden fallback to Home Assistant home coordinates, cached coordinates or straight-line estimates.

## Release discipline

For every release:

- keep `manifest.json` and `const.py` versions identical;
- update `CHANGELOG.md`;
- keep all CI gates green;
- document every new setting/entity;
- keep endpoint identity stable across movement;
- review diagnostics for secrets/location exposure;
- validate upgrade/reload behaviour in Home Assistant;
- test the released HACS artefact, not only a working-tree copy.
