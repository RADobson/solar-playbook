# Validation record — v0.1.0

Local development validation on 12 October 2026, using CPython 3.13.5 on macOS/ARM64.

## Executed

```sh
python -W error::ResourceWarning -m unittest discover -s tests
python -m solar_playbook demo --out out/sunny
python -m solar_playbook demo --scenario cloudy --out out/cloudy
python -m solar_playbook demo --scenario away --out out/away
python -m solar_playbook demo --ai-config examples/ai-config.json --out out/portable
python scripts/collect_sources.py
```

The automated suite passes. It includes randomised energy-conservation checks, EV deadline/availability and target constraints, inverter/battery/import limits, stale-data failures, provider request/response shapes, API failure fallback, persistent request allowances, HTML escaping and command-line replay.

Sunny, cloudy and away scenarios select feasible reference schedules. The impossible/stale cases fail explicitly, as expected. The disabled cloud configuration makes no provider request. The source-collection plan validates pinned upstream revisions without installing upstream code.

## Not yet verified

- Real Sigenergy, Tesla, ESP32, HomeKit pairing or HA installation.
- Live BoM product parsing/download and roof-specific forecast calibration.
- Actual paid AI requests, provider-model compatibility or real API billing limits.
- Local Ollama installation or inference performance.
- ARM Raspberry Pi / x86 Linux execution and resource usage; Docker build/run.
- GitHub-hosted CI until the repository is published and its runs complete.
- A rendered browser screenshot of the HTML report. Structural/escaping and output tests pass, but local server binding and browser file-URL preview were unavailable in this build environment.
- Live control, lease enforcement, watchdog, unattended daemon or recovery behaviour. Those components are not represented as implemented in v0.1.

The source manifest was checked against GitHub commit references. These are research snapshots, not a tested compatibility set. Package/source download limitations did not affect the dependency-free core tests.
