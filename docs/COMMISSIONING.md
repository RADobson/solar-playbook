# Commissioning and operating the system

v0.2 has a tested software contract for one attended evcc mode handoff. It has **no field-qualified equipment combination or unattended supervisor**. Follow the [compatibility evidence levels](COMPATIBILITY.md); a successful test suite is not a completed installation.

## Ownership record

Keep a private sheet containing exact regional models/SKUs, usable battery capacity, firmware, HA/integration/ESPHome revisions, evcc version/driver, installation limits, entity mapping, units and signs, forecast product, rate limits, tariff dates, key custodian, upstream entitlement, fallback settings and recovery contacts. Use the [template](../examples/commissioning-template.md). Never commit real credentials or the completed household sheet publicly.

Identify the physical grid meter, charger circuit and vehicle/session separately. Record the one owner of charger settings and the one owner of battery settings. Record who can change a mode manually and which controls remain usable during an outage. For a three-phase site, commission phase-aware limits independently; the current single-phase simulator does not establish them.

## Read-only acceptance

1. Confirm the chosen meter interface is enabled through the supported installer/vendor process and reachable only on intended network paths. For Sigenergy this includes local Modbus; a separate meter or HA integration needs its own installation checks.
2. Compare HA readings with the manufacturer's app and meter while a known load starts/stops. Resolve inconsistent grid/battery signs before any scheduling.
3. Verify timestamp age and device poll freshness. Test a disconnected device: it must become unavailable, not a plausible frozen value.
4. Verify the vehicle/session association and charge-point identity. For a Tesla BLE route, check the correct paired car and sleep recovery. For evcc, check the loadpoint name, connection state and optional vehicle mapping. An OCPP station ID is not a VIN.
5. Record at least seven days of telemetry. Reconcile energy integrals against daily counters, allowing documented measurement/conversion differences.

Meter receipt timestamps, HA state times and actual device sampling times have different meanings. Current normalized readings retain that distinction and remain ineligible to authorise control. Test the active controller's meter-loss behavior independently of the Python reader. See [metering](METERING.md).

For optional BYD or other vehicle telemetry, confirm the country/account, actual `%` entity, timestamp source, capacity basis and freshness while the car sleeps. Do not publish a percentage-target support claim until the exact model/account path works. The offline energy request remains the useful baseline.

## Before the attended evcc handoff

Define a native fallback that achieves a useful minimum charge. Confirm which evcc/charger settings persist after software failure and demonstrate an ordinary charge without Solar Playbook. The fallback needs to remain understandable if evcc itself is unavailable. Record and resolve any competing charger, vehicle, tariff-service or HA schedules; retain electrical safeguards.

For a Tesla BLE route, measure actual range, wake latency and success rate in the normal parking position; that route remains separately unimplemented in this project. For the evcc route, test the exact driver and charger firmware with evcc directly, including minimum current, measured power, pause/resume and recovery. Prefer reliable networking and record the selected upstream sponsor entitlement.

Pin the adapter contract to evcc **0.317.1** and complete the gates in `private/charger.json`: the actual loadpoint name/index, optional vehicle binding, conservative commissioned current and phases, `commissioning_id`, `control_enabled`, `independent_limits_verified` and `fallback_verified`. The booleans record completed work; setting them does not perform the tests.

Use `evcc-read`, then a `charge-mode` preview. Check version, readiness, connected state, expected mode and allowlist. `smart` follows the full existing evcc policy, which can include grid/tariff and battery behavior; inspect that policy before using the name as a solar promise. The sample excludes `now` until it is deliberately allowed. See the exact [commands](INTEGRATIONS.md).

Only during an attended test add `--apply --attended`. Watch the physical equipment after the command. A receipt reporting `controller_mode_verified` does not prove charge current or delivered energy. If the result is `unconfirmed`, inspect the actual state before deciding whether any further action is required. Do not add an automatic retry loop.

The resulting mode persists. The request time window only bounds preflight. The original `proposal_gate` is still a pure function; neither that function nor the new CLI supplies a watchdog, automatic restoration or execution of the simulator's current trajectory. Manual changes can race a request, so a successful expected-mode check does not authorise unattended operation.

## Attended control acceptance matrix

The matrix is the real-site exit criterion, **not a list of completed v0.2 features**. Current adjustment and fast control must be tested through the selected controller/driver. Owner-expiry, continuous fallback and automatic replan behavior require the future supervisor before they can pass an unattended gate.

| Exercise | Required result |
|---|---|
| Start at minimum current | Command and measured current agree; installed limits honoured |
| Change current | Apply only allowed values; verify resulting telemetry |
| Stop/pause | Confirm stopped state and explain any vehicle-specific delay |
| Unplug or leave home | Withdraw control eligibility and invalidate pending actions |
| Manual charge-now request | Owner request wins; visible expiry; native SOC target preserved |
| Forecast unavailable/stale | Use documented fallback; no fabricated sunshine |
| Meter, HA, charger/evcc or optional BLE link lost | Fault visible; no new unverified commands; verify actual device behaviour |
| Timeout after mode POST | Mark outcome unknown; inspect controller/equipment before any further action |
| Shared charger / guest car | Correct identity or conservative guest behavior; no percentage target borrowed from another car |
| Planner crash/restart | No duplicate action; no stale-plan replay; safe ownership re-established |
| Host reboot, power loss, or disk-unlock/login pending | Native fallback remains understandable and recoverable |
| AI provider outage or allowance exhausted | Local scheduling continues; explanation falls back; no retry storm |
| Conflicting native schedules | Conflict detected or eliminated before unattended use |
| Battery approaches reserve/full | No forbidden discharge/charge request; energy model matches native behaviour |
| Approved grid/export limit changes | Site configuration revised through the responsible process; never silently increased |

Log observed results, not just “command returned 200.” Start with one EV and a qualified charger/meter combination. Gate unattended operation on the additional [supervisor and recovery requirements](MULTIBRAND_DESIGN.md), not merely an attended mode success. Add battery work-mode control only when its extra value and recovery behavior are demonstrated.

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
