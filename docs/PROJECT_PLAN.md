# Project plan

## The outcome

The household plugs in the car, chooses when it must be ready, and carries on with life. The system uses locally measured energy flows, electricity prices and forecasts to select a sensible charging schedule. An Apple Home control provides an immediate override. The explanation is short enough to be useful: “Charge after 9; the cheap window covers the cloudy morning. Keep the house reserve.”

The first deployment profile is a single-phase Sigenergy hybrid system and a Tesla charging from a separately installed AC Wall Connector. The platform is hardware agnostic: a suitable Raspberry Pi, small x86 PC, server or Mac can host it. Prefer a modest, dependable, always-on device. Cloud AI is optional and needs no local GPU. Installations may use a qualified customer device or an installer-supplied appliance.

The public example uses 18 kW of panels and a 10 kW AC inverter, with a **hypothetical** 20 kWh battery. Real battery capacity, charge power, panel strings, service limits and tariffs must be entered from the commissioned installation. Hardware purchasing and network approval remain separate from software planning.

## A SOAR-style architecture

Think of the system as a playbook with five stages:

1. **Collect:** local Sigenergy telemetry, Tesla state, household preferences, tariff intervals, weather and roof-specific solar forecasts.
2. **Normalise:** units, timestamps, sign conventions, confidence and provenance. “Unknown” remains unknown; it does not become zero load or a full battery.
3. **Plan:** evaluate energy trajectories and select a feasible schedule. The current implementation compares five strategies. A later EMHASS backend can solve a richer mathematical optimisation problem.
4. **Enforce:** a future, separately commissioned actuator checks current site state, manual ownership, a short command lease and electrical limits before allowing a command. A good forecast cannot override a failed safety check.
5. **Explain and audit:** record inputs, candidate plans, selected plan, rejected conditions and later measured outcomes. An optional provider-neutral AI adapter turns a numeric summary into plain language. OpenAI, Claude and compatible APIs are supported interfaces; local Ollama remains optional.

The control authority order is physical equipment protection, commissioned site limits, owner override, deadline requirements, deterministic scheduling, then optional AI advice. AI has no authority to change protection settings.

## What runs where

| Location | Responsibility | Initial resource allocation |
|---|---|---|
| Local ARM64 or x86-64 host | Home Assistant, dashboard, HomeKit Bridge, later enforcement | Qualify a 4 GB-class host; no GPU required |
| Portable Python process or container | Planner, replay, reports; later scheduling service | Runs on the same host or another LAN device |
| Optional remote AI API | Explanation and bounded suggestions | Short HTTPS requests; request allowance; owner-approved provider |
| ESP32 near driveway | Authenticated BLE link to Tesla, reached through Wi-Fi | Board-specific upstream firmware |
| HomePod mini or Apple TV | Remote Apple Home access and Apple-side automations | Separate from HA and the planner |

The core uses Python's standard library and does not depend on a CPU instruction set, Apple framework or particular AI vendor. Network reachability and hardware integrations are separate adapters. If virtualised, use networking that supports the required LAN discovery and connections. HA OS app packaging is the intended appliance route; the present CLI and Docker recipe are the development route.

These allocations are starting assumptions, not a hardware certification. Confirm the existing Pi's model, reliable storage, cooling, power supply and recovery after power loss. Benchmark planner duration and HA responsiveness on both ARM64 and x86-64 before calling them commercially supported. A BYO acceptance checklist controls support variability; a supplied appliance provides a predictable alternative.

## Decisions that reduce household admin

**Keep normal charging available.** The system should still be useful when the host, Wi-Fi, internet or AI provider is unavailable. Local scheduling does not require a cloud AI response. Commission a documented native Tesla/Sigenergy fallback for host failures and test it; do not assume every remembered EV current limit resets automatically.

**Make preferences durable.** Owner-managed target SOC, departure time and battery reserve live in a small site configuration. Reconfiguration after an update must not require reading Python. This alpha uses explicit JSON; a guided UI is a later milestone.

**Have one active writer.** Native Sigenergy AI, a third-party optimiser, a Tesla schedule and this project can otherwise fight one another. Record which component owns each setting. Begin with read-only monitoring, then EV control only, then consider battery control if measured benefits justify it.

**Keep the household interface small.** Automatic, charge now, pause until a chosen time, and a clear status. Home Assistant remains the engineering dashboard; Apple Home is the household front door. Do not expose inverter work-mode registers in Apple Home.

**Put overrides above savings.** Charge now means accept grid energy if necessary within the installed limits. It must not require an argument with the optimiser. Expire temporary overrides visibly and record who/what requested them.

## The 18 kW / 10 kW model

The panel rating is DC; the inverter rating is AC. A compatible DC-coupled hybrid can route some panel energy to the battery without converting all of it to AC first. Our simulator implements this split. For example, 18 kW available at the DC bus can serve close to 10 kW AC and also charge the battery, subject to conversion losses, battery headroom and DC charging limits.

Once the battery is full, instantaneous usable power depends on house demand, EV demand, export permission and the AC limit. Clipping is then possible. The extra panels can still help in weak light and at the shoulders of the day. Actual input-voltage/current/string compliance must be checked against the exact inverter and panel variants; the nameplate arithmetic alone is insufficient.

Zero feed-in payment changes the economics, not the electrical export setting. Consuming surplus is attractive when it displaces a future paid purchase. Cycling a battery unnecessarily, overcharging a car beyond the requested target, or warming an empty house solely to report “zero export” is not automatically valuable.

## Development stages and exit criteria

| Stage | Deliverable | Exit criterion |
|---|---|---|
| 0 — This repository | Simulator, candidate planner, reports, parser, read adapter, advisor, plan | Automated tests pass; alpha limitations visible |
| 1 — Observe one real home | HA integrations, units/signs, forecast cache, local logging | Seven complete days; all key telemetry timestamps and energy totals reconcile |
| 2 — Shadow planning | Automatic forecast ingestion, actual tariffs and measured load forecast | Two weeks of plans; deadline feasibility checked; compare predicted and actual PV by hour |
| 3 — EV control | Site-specific actuator, feedback, watchdog, single-writer ownership, override | Owner-attended tests pass, including host restart, Wi-Fi loss, stale forecast and car unplugging |
| 4 — Battery coordination | Native supported controls or metering integration, rollback | Clear extra benefit over EV-only; commissioned power and reserve constraints survive failures |
| 5 — Installer pilot | Reproducible image/config, remote support with consent, handover pack | 3–5 similar homes; installation/support time and outcomes measured |

These are acceptance gates, not promised calendar dates. A useful home setup may stop at stage 3. A business needs repeatable stage 5 evidence before broad sales.

## Build versus reuse

Reuse Home Assistant, the Sigenergy local Modbus integration, ESPHome Tesla BLE, and a proven forecasting source. Keep their source and licences identifiable. Our custom work is the site contract, comparison/replay harness, explanations, commissioning workflow and eventually tightly bounded orchestration.

Before expanding our planner into a full optimiser, compare EMHASS and evcc against the supported profile. EMHASS is a candidate scheduling backend; evcc may replace much of the EV-control layer. Adding a second optimiser is not a default requirement. Predbat is relevant competition, but its current personal-use licence prevents assuming it belongs in an unrestricted commercial bundle.

## Things to measure before adding complexity

Record car-at-home hours, actual charging efficiency, PV forecast error, base-load predictability, departure success, override frequency and incremental grid cost. Compare against a simple native cheap-window schedule, not against “no automation at all.” A cheap daytime tariff may already capture much of the financial benefit.

An AI service earns its place if explanations, preference capture or troubleshooting save owner time. It does not earn its place by choosing cloud conditions more confidently than a numerical weather model. Forecast uncertainty should be represented explicitly and replanning should use fresh measurements. Use a few event-driven or daily AI calls, not one request per telemetry poll. Keep API spending, weather-feed costs and optional support fees separate.

## Open questions for actual commissioning

- Exact battery usable capacity, supported DC charge/discharge power, firmware and external-control behaviour.
- Approved inverter/export limits, service capacity and installation of any required metering/load management.
- Tariff rates, validity dates, weekday/weekend rules and exceptions; zero feed-in rate confirmed separately from export permission.
- Tesla firmware compatibility, BLE range, supported charging-manager role and true charge state/plugged-in telemetry.
- Roof orientations, tilt, shading, DC string details and suitable solar forecast representation for a shared hybrid inverter.
- Owner departure patterns, acceptable minimum SOC, storm reserve preference and override duration.

The project remains useful while these are resolved: run simulations, qualify an available host and learn from read-only telemetry first.
