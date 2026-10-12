# Validation record — v0.2.0

Local validation on 13 October 2026 using CPython 3.14.3 on macOS/ARM64. Tests use synthetic data and injected transports; they do not contact household devices or paid APIs.

## Executed locally

```sh
python -W error::ResourceWarning -m unittest discover -s tests
python -m solar_playbook demo --out out/sunny
python -m solar_playbook demo --scenario cloudy --out out/cloudy
python -m solar_playbook demo --scenario away --out out/away
python -m solar_playbook demo --ai-config examples/ai-config.json --out out/portable
python -m solar_playbook device-demo --out out/devices
python -m solar_playbook demo --vehicle-request examples/vehicle-offline.json --out out/vehicle
python scripts/collect_sources.py
```

The suite covers energy conservation, EV deadlines/availability and targets, inverter/battery/import limits, stale-data failures, AI request/response shapes and fallback, request allowances, report escaping and CLI replay. New integration coverage includes:

- Shelly and Home Assistant meter parsing, units/sign, source provenance, invalid responses, stale captures and receipt-only timestamps.
- Offline wall/battery energy requests and SOC-derived requests actually changing planner input; unknown/stale/future SOC and identity mismatches fail explicitly. A live-read regression checks freshness against the clock after the response arrives.
- Exact evcc mode routes, identity/version/readiness/current/phase gates, preview without POST, attended apply, idempotent selection, readback mismatch, ambiguous writes without retry and preserved outcomes when receipt storage fails.
- A complete offline device example with network access rejected by the test transport and zero hardware writes.

Sunny, cloudy and away scenarios produce feasible reference schedules. Impossible/stale cases fail explicitly. The disabled cloud configuration makes no provider request. The source-collection plan validates pinned manifest entries without installing upstream code.

## Continuous integration

The published v0.1 tree passed GitHub-hosted tests and its demo on Python 3.11–3.13. The v0.2 workflow runs tests and both demos on Python 3.11–3.14 on Ubuntu 24.04. Check the [Actions page](https://github.com/RADobson/solar-playbook/actions) against the commit being installed; workflow configuration alone is not evidence that a particular commit passed.

## Not yet verified

- Real Sigenergy, utility meters, Shelly, evcc chargers, Tesla/BYD telemetry, ESP32, HomeKit pairing or HA installation. No device/model/firmware combination is field-qualified by this release.
- Live BoM download/parsing and roof-specific forecast calibration.
- Actual paid AI requests, provider-model compatibility or real billing limits.
- Raspberry Pi resource usage, container build/run or local Ollama performance.
- Physical behaviour after an evcc mode change. The adapter verifies controller state, not current flow. It does not implement an unattended supervisor, hardware lease, watchdog, automatic recovery or rollback; selected modes persist.
- Rendered report visual QA. Structural/escaping tests pass, but a local report preview was unavailable in this build environment.

The evcc adapter contract was reviewed against upstream 0.317.1 and tested with fixtures. Upstream pins are research snapshots, not a tested hardware compatibility set. See [commissioning](COMMISSIONING.md) and the [compatibility matrix](COMPATIBILITY.md) for the next validation steps.
