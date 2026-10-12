# Software collection and licences

The core Solar Playbook package has no third-party runtime dependencies. Its source is MIT licensed. This does **not** relicense any linked component, model, API or dataset.

## Collected source references

`upstreams.lock.json` records exact upstream research snapshots and their verification metadata. These are not a claim that the combination has passed commissioning. The v0.2 evcc HTTP contract targets **0.317.1**; qualify that interface and the selected device driver independently of the collection manifest. The source-collection helper validates the manifest, downloads separate checkouts, verifies their SHAs and does not execute upstream code.

```sh
python3 scripts/collect_sources.py             # inspect the collection plan
python3 scripts/collect_sources.py --download  # requires git and internet
```

Checkouts go under ignored `out/upstreams/`. Existing directories are never overwritten. Keep upstream LICENSE/NOTICE files with source distributions. The helper's plan mode was run locally; downloading all source was not completed in the build environment, which could not resolve external package hosts. Use a normal network-enabled development machine for collection.

| Project | Role | Licence / important boundary |
|---|---|---|
| [Home Assistant](https://github.com/home-assistant/core) | Integrations, household UI, HomeKit Bridge | Apache-2.0 for core; OS/apps have separate components/licences |
| [Sigenergy Local Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus) | Local inverter telemetry and optional controls | MIT; community integration; begin read-only |
| [ESPHome Tesla BLE](https://github.com/yoziru/esphome-tesla-ble) | ESP32-to-vehicle link | AGPL-3.0; preserve corresponding-source and notice obligations when applicable |
| [EMHASS](https://github.com/davidusb-geek/emhass) | Candidate advanced scheduling backend | MIT; not required by v0.2 |
| [evcc](https://github.com/evcc-io/evcc) | Implemented HTTP adapter boundary; separately installed charger controller | MIT core; device sponsorship and service/commercial terms remain separate |
| [BYD Vehicle for HA](https://github.com/jkaberg/hass-byd-vehicle) | Optional upstream source for explicitly mapped SOC telemetry | MIT community integration; BYD account/service rights and exact model qualification are separate; no BYD source is bundled here |
| [HA Solcast integration](https://github.com/BJReplay/ha-solcast-solar) | Optional personal solar forecasting integration | Apache-2.0 software; forecast-account rights are separate |
| [Ollama](https://github.com/ollama/ollama) | Optional local model host | MIT software; individual model weights have separate licences |
| [Predbat](https://springfall2008.github.io/batpred/) | Comparison / alternative ecosystem | Current personal-use licence; not included in this unrestricted commercial baseline |

Home Assistant images and optional model weights should be downloaded from their official distributors. They are not copied into this small source repository. Container base images and CI actions remain external build inputs; a production release needs digest-pinned images, an SBOM and a tested update policy.

## evcc entitlements and commercial deployment

The MIT source licence permits commercial use subject to its notices. Official evcc builds require sponsor tokens for many charger adapters, including the Fronius Wattpilot and Wallbox Pulsar Plus candidates. The upstream offers recurring and one-time routes, plus installer token bundles for customer hardware installations. Tokens may not be sold separately. Verify the current terms and entitlement for each site before quoting; do not copy one customer's token into every appliance. [evcc sponsorship and installer terms](https://docs.evcc.io/en/sponsorship/)

The current experimental load-management documentation flags a separate commercial-use licence planned for the future. Sponsor access alone should not be represented as a perpetual entitlement to every commercial feature. Review that scope before promising a multi-charger product. [Load-management restrictions](https://docs.evcc.io/en/features/loadmanagement/)

Solar Playbook does not remove token checks or package upstream cloud accounts. Supply source notices, recorded versions, customer-owned credentials and a handover/renewal record. A no-recurring-fee installation is a configuration to verify, not an automatic consequence of open source licensing. Check optional weather, metering, vehicle API and AI service costs separately.

## Why not put every upstream file in one folder?

A source manifest plus reproducible collection preserves update provenance and licence boundaries. Blindly copying all dependencies obscures ownership and makes security fixes harder. A commercial appliance release should archive the exact source/build inputs used for that release and meet redistribution obligations, including modified firmware source where required.

Do not treat “free to access,” “source available,” “open source,” “free personal tier” and “licensed for commercial service” as interchangeable. The [weather guide](WEATHER.md) and [AI guide](AI_PROVIDERS.md) cover service-specific terms and budget controls.
