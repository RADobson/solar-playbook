# Meter, vehicle, charger and Apple Home integrations

These procedures are independent of the host hardware. Start with [compatibility and qualification](COMPATIBILITY.md), then read data before considering an attended handoff. v0.2 provides readers and a deliberately small evcc mode-write boundary. It does not automatically install Home Assistant, evcc, a vendor integration or a household control loop.

## Run the complete offline example

```sh
python3 -m solar_playbook device-demo --out out/devices
python3 -m solar_playbook demo --vehicle-request examples/vehicle-offline.json --out out/offline-car
```

The first command writes `report.html`, `report.json`, `devices.json`, the scenario input and replayable meter/request fixtures. It uses no network and never calls a controller. The second uses a 15 kWh **wall-side** energy request with 90% assumed efficiency, so the planner models 13.5 kWh reaching the battery. No vehicle brand or account is required.

`devices.json` intentionally keeps the meter observation, planning result and mode preview distinct. A single current grid-power reading is not a day-ahead forecast, and a mode preview does not execute the simulated schedule.

## Read a grid meter

Copy the appropriate sample to an ignored private location, then replace the documented placeholders:

```sh
mkdir -p private
cp examples/meter-home-assistant.json private/meter.json
python3 -m solar_playbook meter-read private/meter.json
```

For Home Assistant, configure the actual grid-power entity, expected `W` or `kW` unit, import/export sign, origin and token **environment-variable name**. Set that environment variable privately before running. Never put the token itself in JSON, a command argument, a Git issue or a screenshot. A Sigenergy grid sensor uses this same mapping; there is no extra direct Modbus reader in Solar Playbook.

Alternatively copy `examples/meter-shelly.json`. The direct reader uses Pro 3EM `EM.GetStatus`, validates meter/phase errors and normalizes total power. **Shelly digest authentication is not implemented**: for a protected device, use its authenticated HA integration rather than disabling device authentication. The adapter reads no phase currents, changes no calibration and performs no device writes.

Positive `grid_power_kw` means import and negative means export. The result records timestamp provenance. HA timestamps are not proof of a new physical measurement; the Shelly direct response supplies receipt time rather than an internal sampling timestamp. Every current meter result has `control_eligible: false`. See [metering](METERING.md).

You can replay the generated synthetic meter at its original time:

```sh
python3 -m solar_playbook meter-read out/devices/meter-fixture.json --at 2030-01-15T00:00:00+00:00
```

`--at` is only allowed for fixtures. Never change the reference time to make a stale live feed appear current.

## Optional vehicle SOC

`examples/vehicle-offline.json` is the useful baseline. It states `mode: add_energy`, `energy_kwh`, `energy_basis` (`wall` or `battery`) and `charging_efficiency`. It cannot discover a car's actual percentage or guarantee that the vehicle accepts all the requested energy.

For a percentage request, copy `examples/vehicle-byd-ha.json` into `private/`, replace the hypothetical battery capacity and HA entity, and choose a verified timestamp field. The file's name illustrates a BYD route, but its implementation is a generic HA SOC sensor contract; it neither logs in to BYD nor controls the vehicle.

```sh
cp examples/vehicle-byd-ha.json private/vehicle.json
python3 -m solar_playbook demo --vehicle-request private/vehicle.json --out out/soc-plan
```

The telemetry configuration names its private token environment variable, the exact `%` sensor, and either a documented `attributes.<source_timestamp>`, `last_reported` or `last_updated`. Prefer a true source timestamp. HA-only timestamps leave an explicit freshness limitation in the result. Unknown, non-finite, stale or future SOC is rejected; it is not converted to zero SOC.

`--vehicle-request` also works with `plan INPUT`. A previously saved, reviewed HA-state fixture may be supplied with `--vehicle-state PATH`; `--at` is permitted only with that fixture and affects replay time, never live reads. Availability and departure still come from the scenario. An energy request or SOC request changes the simulation input only; it does not send a deadline, energy target or vehicle charge limit to evcc.

## Read evcc and preview a mode

Configure evcc's own meter, charger and limits first. Pin and qualify the **0.317.1** interface expected by this release. Copy the sample and replace the origin, loadpoint identity, optional vehicle name and actual commissioned limits:

```sh
cp examples/charger-evcc.json private/charger.json
python3 -m solar_playbook evcc-read private/charger.json
python3 -m solar_playbook charge-mode private/charger.json smart --expected-mode off --out private/preview.json
```

Set `EVCC_TOKEN` privately if the configured deployment requires it; `token_env` names the variable and may be null only when the commissioned deployment does not use an API token. A sample origin or loadpoint placeholder is not a discovered device. Keep evcc on a trusted network and use its supported authentication rather than exposing it to the internet.

The preview reads real controller state but makes no changes. It may report ineligible while commissioning flags are false; that is the sample's intended state. The configured loadpoint index is checked against its expected name because indices can move. An optional expected vehicle name adds a binding check; it does not independently identify the plugged-in car.

| Mode | Meaning at the boundary |
|---|---|
| `off` | Ask evcc to stop its charging mode; inspect physical behavior |
| `smart` | Use the existing evcc policy, including configured tariffs, plans and battery behavior; not necessarily solar only |
| `now` | Request immediate charging under existing evcc/charger limits; may import grid power |

The sample allows only `off` and `smart`. Adding `now` is an explicit commissioning choice. Solar Playbook never adjusts the controller's maximum current or phase settings to make a request pass.

## Optional attended application

After the [commissioning procedure](COMMISSIONING.md), record `commissioning_id`, set `control_enabled`, and truthfully set `independent_limits_verified` and `fallback_verified`. The adapter also checks controller version/readiness, physical connection reported by evcc, expected mode, configured loadpoint/optional vehicle identity, current/phase bounds, mode allowlist and the short preflight request window.

During an owner-attended test, this command can make **one real, persistent change**:

```sh
python3 -m solar_playbook charge-mode private/charger.json smart --expected-mode off --apply --attended --out private/handoff.json
```

Use the actual currently expected mode. A mismatch blocks the request; never script around it by blindly replacing the expectation. On success, a second read verifies evcc's mode, **not physical charging**. Independently observe the charger/car during commissioning.

The resulting mode persists after the command exits. `max_request_seconds` bounds preflight, not the life of the mode. There is no automatic restoration, watchdog or continuous interlock. A timeout after POST leaves an unknown outcome: inspect evcc and the equipment before any further action; do not blindly retry. The expected-mode comparison cannot eliminate a simultaneous manual-UI race, which is another reason this interface remains attended.

evcc must remain the sole charger writer. Do not point the charger at a second HA OCPP controller or run competing current-setting automations. The original planner's `proposal_gate` is still a pure function and does not run its simulated charging trajectory.

## Module interfaces

| Module API | Input / output and authority |
|---|---|
| `metering.read_meter(config)` | One configured local/HA poll or fixture → `MeterReading`; kW and provenance, always ineligible to authorise control |
| `vehicles.resolve_vehicle_request(config, now=..., state=...)` | Energy or SOC request → `VehicleRequestResult`; required battery kWh, efficiency, assumptions and provenance |
| `charging.ChargerConfig.from_dict(config)` | Strict evcc adapter configuration; credentials are referenced by environment-variable name |
| `charging.Evcc(config).read()` | GET controller state → `ChargerReading`; receipt time does not prove device-data freshness |
| `charging.handoff_mode(config, mode, expected_mode=...)` | Preview by default; explicit `apply=True, attended=True` can POST one allowed mode and read back controller state |

When using `VehicleRequestResult` from Python, set both `Scenario.ev_required_kwh` and `Site.ev_efficiency` from its returned values to preserve the wall/battery energy distinction. The CLI does this for `--vehicle-request`. Test injection hooks are for trusted fixture transports, not an alternative way to authorise writes.

## Sigenergy integration

Use the installation instructions in [Sigenergy Local Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus). Record the integration commit/release, HA version and inverter firmware. Begin in its read-only mode.

Ask the installer to enable the supported local Modbus interface and confirm network access during commissioning. Modbus is a communications protocol, not necessarily an extra box. If the installer leaves it disabled, installation of the HA integration alone cannot turn an unreachable interface into a working feed. Check the permitted enablement process with the installer/vendor. Do not bypass installer credentials or substitute guessed settings.

Compare PV, battery SOC, battery power, grid power and house load against the native app and a real load change. Establish the sign convention for import/export and charge/discharge. Record the exact entity IDs and units. HA reporting freshness is not proof of fresh device data: inspect an actual device poll/heartbeat too.

## Tesla BLE link

Follow the current [ESPHome Tesla BLE installation guide](https://github.com/yoziru/esphome-tesla-ble) for the **exact board**. The generic ESP32 package is not interchangeable with C3/S3 variants. Flashing, encryption and key provisioning should follow the pinned upstream instructions.

Place the board near the parked car, with reliable Wi-Fi and power. Pair it through the Tesla's supported key process with the owner physically present. Prefer the charging-manager role where supported and adequate. Keep VIN, vehicle key material, Wi-Fi passwords and ESPHome API/OTA secrets out of Git. Test wake, state readout and charging capabilities separately.

The path is HA → Wi-Fi → ESP32 → authenticated Bluetooth → car. The Wall Connector continues to supply AC subject to its electrical limits. Do not open or modify its electronics to build this integration.

This alpha does not issue BLE commands. The new evcc mode adapter is a separate control route. Any future BLE actuator needs its own physical feedback and commissioning; a successful HTTP call to HA is only an acknowledgement.

## Apple Home

Home Assistant's [HomeKit Bridge integration](https://www.home-assistant.io/integrations/homekit/) is software running inside HA. Add it under Devices & Services, select an explicit allowlist of useful entities and pair its code in Apple Home. Avoid exposing all entities by default.

`integrations/home_assistant/solar_playbook.yaml` supplies request helpers and an example allowlist. Merge configuration with an existing setup rather than creating duplicate HomeKit bridges. These helpers are not wired to the attended CLI and do not operate equipment in v0.2. Target percentage and departure date/time stay on the HA dashboard initially because HomeKit does not have a native general-purpose energy-scheduling form.

For remote Apple Home access and Apple-side automations, configure a supported HomePod/Apple TV home hub. It is not a replacement for HA or the ESP32. The basic energy decision loop can remain local independently of remote Apple access.

## First read-only check

Create a suitable HA token through your own HA account and put it in the `HA_TOKEN` environment variable without sharing it. The alpha reads one configured entity at a time and never calls HA services. HA tokens can carry significant authority even when our client only performs reads; protect and revoke them accordingly.

Record successful reads, firmware versions and site limits in a private commissioning sheet. Do not upload that sheet or real telemetry to the public repository without reviewing and anonymising it.
