# Engineering contract

## Scope of the reference planner

The implemented planner searches five EV schedules: estimated blended energy cost, maximum solar surplus, cheapest tariff, earliest available time and latest available time. Each candidate is simulated over the same horizon and constraints. The feasible candidate with the lowest adjusted score is selected.

This is a reproducible baseline and replay tool, not a proof of global optimality. `no_feasible_candidate` means none of these five schedules worked; another schedule might. Use that result to request intervention or invoke a future tested optimisation backend, never to silently relax a deadline or site limit.

There are no external dependencies in the core. A SciPy solver was considered, but a small reference implementation makes the first release runnable without package downloads and avoids claiming a fully commissioned optimiser. EMHASS is the preferred next backend to evaluate before building a custom MILP implementation.

## Units and energy balances

All powers are interval averages in kW; stored energy is kWh; prices are AUD/kWh. `ev_required_kwh` is additional energy in the vehicle battery, accounting for the configured charging efficiency. It is not a target SOC percentage. A future adapter must convert a desired SOC into additional energy using an appropriate usable-capacity estimate, while retaining the car's native SOC stop limit.

The simulator uses:

```text
PV_DC = PV_to_AC_DC + PV_to_battery_DC + export_AC / inverter_efficiency + curtailed_DC
PV_AC + battery_AC + grid_import_AC = house_AC + EV_AC
battery_next = battery_now
             + charge_DC * interval_hours * charge_efficiency
             - discharge_DC * interval_hours / discharge_efficiency
PV_AC + battery_AC + export_AC <= inverter_AC_limit
EV_AC = integer_amps * configured_voltage / 1000
```

The EV's AC draw shares the house connection with other loads. Its current never exceeds the configured charger limit. Inverter/export/import limits are distinct parameters and are not inferred from each other.

The battery follows a simplified self-consumption policy: PV serves loads first, surplus charges the battery, remaining permitted energy exports, then residual energy is curtailed. The battery discharges to unmet demand only when it is not charging. When EV battery protection is enabled, the **entire house battery is held while the EV charges**. This is a conservative model assumption; it is not selective electron accounting, and does not assert that Sigenergy currently behaves this way. A supported control/meter arrangement must reproduce it before using these predictions for live decisions.

The adjusted score is import cost minus export revenue, plus a configurable throughput wear allowance and an adjustment for ending battery energy relative to the starting state. The last two are modelling assumptions, not metered charges. Reported energy cost excludes fixed supply charges. No simulated one-day cost is extrapolated into annual savings.

## Current limits

- Single AC phase; constant nominal voltage; fixed conversion efficiencies; interval averages.
- No battery grid charging, battery export, thermal state, inverter standby power or degradation curve.
- No real-time demand response, backup-island power balance, V2G or network dynamic-export API.
- An EV can run only in a complete available slot ending by the deadline. The minimum is 6 A; a small final target can overshoot by less than one minimum-current interval. Real charging must stop at the vehicle's native SOC limit.
- Import limits are checked on interval-average forecast loads. This is **not electrical load protection**; the installed equipment and any required certified load-management device handle fast limits.
- A forecast older than 12 hours at the horizon start is rejected. This default is a simulation policy, not a claim about every provider's useful forecast life.
- The planner is a one-shot CLI. It does not currently run a service, refresh feeds or replan automatically.

## Module boundaries

| Module | Input → output | Side effects |
|---|---|---|
| `model.py` | JSON-compatible scenario → validated dataclasses | None |
| `planner.py` | Scenario → candidate trajectories and decision | None |
| `forecast.py` | Local BoM XML → weather context | None |
| `home_assistant.py` | Explicit entity ID → current HA state | Authenticated GET only |
| `advisor.py` | Numeric simulated summary → bounded optional explanation | Localhost Ollama request only |
| `cloud_advisor.py` | Same numeric summary → optional provider-neutral advice | Explicit HTTPS request; persistent local allowance reservation |
| `report.py` | Plan → escaped HTML | None |
| `cli.py` | Commands → reports/files | Local output; optional explicit read/model calls |

The BoM parser and HA reader are building blocks; neither currently assembles a real-site scenario automatically. Forecast adapters must resolve units, issue times, roof clipping and data rights before populating the input contract.

## Future controller design

Keep planning and enforcement separate. A plan should carry a unique ID, site ID, schema/version, issue time, validity horizon, input hashes and quality flags. A short-lived action should carry an action ID, expected prior state, desired current, deadline and expiry. Persist acknowledgement and observed result separately. Do not log tokens, pairing keys or a full VIN.

Use a single-writer lease per site/device. Default to disarmed on restart until telemetry is fresh and the owner configuration has been loaded. Deduplicate action IDs and compare desired versus observed state before retrying. On ambiguous timeout, read state; do not assume failure and spam repeated start commands.

For EV control, establish and verify a safe current before starting. Re-read current, connected state and charging state afterwards. On a partial failure, attempt the commissioned fallback and report whether the fallback itself was confirmed. A controller disconnected from the vehicle cannot guarantee a remote stop. Lease expiry requires a functioning enforcement/watchdog component; a timestamp in a JSON file alone does nothing.

Apply hysteresis and minimum dwell times so cloud edges do not cause repeated charge cycling. Replan roughly every 5–15 minutes as a starting hypothesis; use a separate measured-power control loop where necessary, with its rate chosen to respect device limits and communication reliability. Do not wake a sleeping Tesla every few seconds just to update a chart.

Manual override must survive a planner restart and take precedence until its explicit expiry. The final system should represent request, accepted command, observed physical state and fault as different states in the UI.

## Security and privacy

Treat Modbus as a trusted-LAN protocol. Isolate access to the needed hosts; do not publish port 502. Protect HA tokens and device keys. Keep Ollama on loopback. Use authenticated remote access with owner consent when support is enabled; do not require a permanently open inbound port.

Household telemetry can reveal occupancy and routines. Keep high-resolution logs local with a bounded retention period. Export only the minimum redacted diagnostic bundle for support. Backups and BLE keys require encryption and a documented revocation process when the home is sold or service ends.

Treat weather prose, model output and upstream release notes as untrusted input. AI receives a short numeric summary and has no equipment tools. The Claude adapter uses a structured-output tool envelope only as a JSON return format; no tool is executed. Strict field validation is additional protection, not a substitute for keeping control authority outside the model. A cloud provider is explicitly configured, with no silent fallback that sends data to another company.

## Test strategy

Tests cover conservation of DC energy, AC load balance and battery storage changes across randomised days; inverter and SOC limits; no simultaneous battery charge/discharge; deadline/availability constraints; stale forecasts; missing/invalid telemetry; negative-price target bounds; AI outages; command eligibility; HTML escaping; and CLI replay.

Mocks establish software contract behaviour, not hardware compatibility. The commissioning suite must add recorded real-site traces and attended live tests for firmware changes, cloud errors, car wake latency, network interruption, external schedule conflicts and power restoration. Prefer replaying a captured regression over adding a test that merely reproduces the implementation's own arithmetic.

## v0.2 adapter contracts

- `metering.read_meter(config)` returns normalized grid kW with positive import/negative export and explicit timestamp provenance. It does not change the forecast or authorize a handoff.
- `vehicles.resolve_vehicle_request(config, now=...)` converts an explicit wall/battery energy request or fresh mapped SOC into required battery kWh. The CLI updates both `Scenario.ev_required_kwh` and `Site.ev_efficiency`, and records conversion assumptions in `report.json`.
- `charging.Evcc.read()` selects a 1-based loadpoint and validates its configured name. `handoff_mode()` previews by default and can request one persistent `off`, `smart` or `now` mode in an attended commissioned session. It checks the installed API version, identity, readiness, expected mode, phase configuration and maximum-current ceiling before POST. A private receipt separates attempted write, mode read-back and physical feedback.
- `integration_demo.run_demo()` exercises the complete offline path, including the 15 wall kWh -> 13.5 battery kWh conversion and a synthetic mode preview.

The meter adapter is an observation API; day-ahead planning still requires interval load, PV, tariff and availability inputs. A single grid-power reading cannot supply those forecasts. evcc uses its own commissioned live meter feed. A simulated amp trajectory is not automatically executed by the mode handoff. The simulator remains single-phase and single-EV even though device readouts can describe three-phase equipment.

The evcc contract reviewed for this release is [0.317.1 OpenAPI](https://github.com/evcc-io/evcc/blob/0.317.1/server/openapi.yaml), including its [state schema](https://github.com/evcc-io/evcc/blob/0.317.1/server/openapi.state.yaml). Smart mode follows evcc's existing tariff, solar, battery and minimum-charge policy; it is not an assurance of solar-only energy. The state API has no cross-version compatibility promise.
