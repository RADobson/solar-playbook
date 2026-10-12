# Commissioning and operating the system

## Ownership record

Keep a private sheet containing exact models, usable battery capacity, firmware, HA/integration/ESPHome revisions, installation limits, entity mapping, units and signs, forecast product, rate limits, tariff dates, key custodian, fallback settings and recovery contacts. Use the [template](../examples/commissioning-template.md). Never commit real credentials or the completed household sheet publicly.

## Read-only acceptance

1. Confirm local Modbus is enabled through the supported installer/vendor process and reachable only on intended network paths.
2. Compare HA readings with the manufacturer's app and meter while a known load starts/stops. Resolve inconsistent grid/battery signs before any scheduling.
3. Verify timestamp age and device poll freshness. Test a disconnected device: it must become unavailable, not a plausible frozen value.
4. Verify the Tesla is the correct paired car, current location/connection are known, and BLE recovery works after sleep. A nearby device is not proof the vehicle is safely plugged in.
5. Record at least seven days of telemetry. Reconcile energy integrals against daily counters, allowing documented measurement/conversion differences.

## Before live EV control is implemented

Define a native fallback that achieves a useful minimum charge. Check whether a low current set by external control persists after software failure. Record which Tesla and Sigenergy schedules remain active and which settings the new controller owns.

Measure actual BLE range, wake latency and success rate in the normal parking position. A board working beside the open door once is not enough. Prefer reliable power and a stable Wi-Fi connection; confirm recovery after router and ESP32 reboots.

The v0.1 `proposal_gate` is a pure eligibility function for future integration. It cannot apply a command, roll it back or enforce an expired lease. Do not describe it as a live watchdog.

## Attended control acceptance matrix

| Exercise | Required result |
|---|---|
| Start at minimum current | Command and measured current agree; installed limits honoured |
| Change current | Apply only allowed values; verify resulting telemetry |
| Stop/pause | Confirm stopped state and explain any vehicle-specific delay |
| Unplug or leave home | Withdraw control eligibility and invalidate pending actions |
| Manual charge-now request | Owner request wins; visible expiry; native SOC target preserved |
| Forecast unavailable/stale | Use documented fallback; no fabricated sunshine |
| HA, ESP32 or inverter link lost | Fault visible; no new unverified commands; verify actual device behaviour |
| Planner crash/restart | No duplicate action; no stale-plan replay; safe ownership re-established |
| Host reboot, power loss, or disk-unlock/login pending | Native fallback remains understandable and recoverable |
| AI provider outage or allowance exhausted | Local scheduling continues; explanation falls back; no retry storm |
| Conflicting native schedules | Conflict detected or eliminated before unattended use |
| Battery approaches reserve/full | No forbidden discharge/charge request; energy model matches native behaviour |
| Approved grid/export limit changes | Site configuration revised through the responsible process; never silently increased |

Log observed results, not just “command returned 200.” Gate unattended operation on passing the relevant tests. Run EV-only first; add battery work-mode control only when its extra value and recovery behaviour are demonstrated.

## Battery coordination options to investigate

First test whether the native Sigenergy configuration already provides the desired behaviour. Supported additional metering may allow the native system to recognise an EV load; verify exact meter model, firmware, wiring and configuration with the installer. A demonstration video is evidence of one working setup, not universal compatibility.

If external EMS control is necessary, document mode transition semantics, power units/signs, timeout behaviour and restoration of native control. Never guess a Modbus register from a different hardware generation. Store an approved register/entity allowlist and reject anything outside it.

## Operating runbook

**Daily:** a household status should state automatic/manual/fallback, last successful measurement and whether the vehicle is on track for departure. Notify for action-worthy faults, not every cloud.

**Monthly:** review missed targets, overrides, forecast bias, host restarts and support incidents. Keep a record of actual user time saved. Check free-feed quotas and token expiry without exposing tokens in logs.

**Updates:** stage changes on the replay suite, back up the working configuration and change one integration at a time. Pin production revisions. Automatic security updates may still be appropriate, but they need a rollback and an owner-visible maintenance policy.

**Recovery:** disable external ownership, restore the recorded native settings, verify a manual charging session and leave the household a one-page instruction card. If connectivity is lost, physical/native controls are the recovery route; a disconnected automation service cannot remotely guarantee a reset.

**End of service:** remove support access, revoke service tokens/device keys as appropriate, return configuration and backups to the owner, and verify independent native operation. Ownership should not be trapped in the installer's cloud account.

## Electrical boundaries

Software does not replace circuit protection, a licensed installation or network connection conditions. Charger/inverter wiring, protective settings, metering installation and supply work belong with the appropriately licensed professionals. In Queensland, providing electrical work to others has licensing requirements; agree the software/electrical split with the installer before selling a combined service. [Queensland electrical contractor licensing](https://www.worksafe.qld.gov.au/licensing-and-registrations/electrical-licences/electrical-contactor-licences).
