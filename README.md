# OpenRouteService Travel Time for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-custom%20integration-41BDF5.svg)](https://www.home-assistant.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A modern Home Assistant custom integration for [OpenRouteService](https://openrouteservice.org/) route duration and distance.

The integration is being built as a standalone HACS integration. It owns OpenRouteService credentials, routing, location resolution and provider-specific error handling, and exposes normal Home Assistant sensors that can be consumed by dashboards, automations or other integrations.

## Development status

**Pre-release / active development.**

The first functional target is walking route calculation using the OpenRouteService `foot-walking` profile with:

- Home Assistant UI configuration;
- fixed or entity-based origins and destinations;
- a Duration sensor;
- a Distance sensor;
- conservative cloud polling;
- reconfiguration and reauthentication;
- translated errors and entity names;
- privacy-safe diagnostics.

## Architecture boundary

This project is independent of BODS Bus Tracker.

BODS may consume the Duration sensor produced here, but this integration has no BODS-specific runtime code and BODS does not own OpenRouteService credentials, coordinates or API behaviour.

## Quality target

The project is engineered against the current Home Assistant Integration Quality Scale, with Bronze, Silver and Gold requirements treated as design requirements from the outset and applicable Platinum technical practices adopted where appropriate.

As a third-party custom integration, this project does not claim an official Home Assistant Core quality-scale tier.

Quality gates will include:

- HACS validation;
- Hassfest;
- Home Assistant-native pytest tests;
- greater than 95% integration test coverage;
- complete config-flow test coverage;
- strict typing;
- lifecycle/unload tests;
- API/coordinator error-path tests;
- diagnostics privacy tests;
- manifest/runtime version synchronisation.

## Installation

The integration is not yet ready for normal installation. HACS installation instructions will be enabled when the first beta is ready for real Home Assistant validation.

## Privacy

OpenRouteService requires route coordinates to calculate a route. The integration will avoid copying precise moving-person coordinates into entity attributes, logs or downloadable diagnostics unless technically necessary.

API keys will be stored in the Home Assistant config entry and redacted from diagnostics.

## Licence

Released under the [MIT License](LICENSE).
