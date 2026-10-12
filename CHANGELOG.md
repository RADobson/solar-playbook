# Changelog

## 0.2.0 — 2026-10-13

- Added portable read-only grid-meter adapters for Shelly Pro 3EM RPC and explicitly mapped Home Assistant sensors, including Sigenergy integrations. Preserve units, sign and timestamp provenance; readings do not authorise control.
- Added offline energy requests and optional HA SOC target conversion with explicit wall/battery energy basis, capacity, efficiency and freshness checks. No direct BYD account or vehicle-control integration is claimed.
- Added `device-demo` to demonstrate meter observation, vehicle request, planning and mode preview offline; added `--vehicle-request` to `demo` and `plan`.
- Added evcc 0.317.1 state reading and default-preview mode handoff. Explicitly enabled attended use can make one persistent mode change, with commissioned-limit, identity, readiness and expected-mode gates and controller read-back.
- Kept evcc as the sole charger writer. No direct OCPP server, current/battery writes, schedule execution daemon, watchdog or automatic restoration is included.
- Added compatibility evidence levels, smart-meter/API guidance, multi-brand architecture, BYD/no-API profiles, qualification procedures and commercial entitlement considerations.
- No real equipment combination has been field qualified. Contract tests and synthetic demonstrations do not establish physical charging success.

## 0.1.0 — 2026-10-12

- Portable Python simulator and five-candidate EV planner with explicit DC/AC flows.
- Synthetic sunny, cloudy, away, infeasible and stale scenarios with JSON/HTML replay reports.
- Read-only Home Assistant adapter, BoM weather-context parser and pure control-eligibility contract.
- Optional OpenAI, Claude, compatible API and local Ollama explanations; disabled by default.
- Persistent AI call allowance and bounded outputs; no equipment tools or automatic provider failover.
- Hardware-neutral plan, BYO/supplied-device service model, commissioning guide and business analysis.
- Pinned upstream source manifest and collection helper.
- No live hardware actuator, unattended daemon, forecast downloader or certified appliance image in this release.
