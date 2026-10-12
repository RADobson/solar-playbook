# Software collection and licences

The core Solar Playbook package has no third-party runtime dependencies. Its source is MIT licensed. This does **not** relicense any linked component, model, API or dataset.

## Collected source references

`upstreams.lock.json` records exact upstream commit SHAs verified through GitHub on 12 October 2026. They are **research snapshots**, not a claim that this combination has passed commissioning. The source-collection helper validates the manifest, downloads separate checkouts, verifies their SHAs and does not execute upstream code.

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
| [EMHASS](https://github.com/davidusb-geek/emhass) | Candidate advanced scheduling backend | MIT; not required by v0.1 |
| [evcc](https://github.com/evcc-io/evcc) | Candidate replacement for EV control/orchestration | MIT core; inspect provider/device/sponsor/service terms separately |
| [HA Solcast integration](https://github.com/BJReplay/ha-solcast-solar) | Optional personal solar forecasting integration | Apache-2.0 software; forecast-account rights are separate |
| [Ollama](https://github.com/ollama/ollama) | Optional local model host | MIT software; individual model weights have separate licences |
| [Predbat](https://springfall2008.github.io/batpred/) | Comparison / alternative ecosystem | Current personal-use licence; not included in this unrestricted commercial baseline |

Home Assistant images and optional model weights should be downloaded from their official distributors. They are not copied into this small source repository. Container base images and CI actions remain external build inputs; a production release needs digest-pinned images, an SBOM and a tested update policy.

## Why not put every upstream file in one folder?

A source manifest plus reproducible collection preserves update provenance and licence boundaries. Blindly copying all dependencies obscures ownership and makes security fixes harder. A commercial appliance release should archive the exact source/build inputs used for that release and meet redistribution obligations, including modified firmware source where required.

Do not treat “free to access,” “source available,” “open source,” “free personal tier” and “licensed for commercial service” as interchangeable. The [weather guide](WEATHER.md) and [AI guide](AI_PROVIDERS.md) cover service-specific terms and budget controls.
