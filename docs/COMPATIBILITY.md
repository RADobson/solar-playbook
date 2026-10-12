# Equipment compatibility and qualification

Solar Playbook separates the **meter**, **charger** and **vehicle**. A different car should not require replacing the household's energy system. Start with a trustworthy grid measurement and a controllable charger; add car telemetry when it makes the experience better.

The v0.2 integration boundary is evcc: Solar Playbook reads data and prepares bounded requests; evcc owns communication with the charger. This project does not implement an OCPP server or a new charger driver.

## What a support claim means

| Status | Evidence required | What it permits us to say |
|---|---|---|
| Implemented / contract tested | Our adapter or conversion code passes synthetic and mocked-interface tests | The documented data contract works in tests |
| Upstream available | A manufacturer or upstream project documents the interface | There is a practical integration route to investigate |
| Field qualified | A recorded test of the exact region, model, firmware, vehicle and wiring at a real site | That specific combination passed the recorded commissioning scope |

**No equipment combination is field qualified by this project yet.** An upstream support listing, passing CI, or a charger accepting an HTTP request does not establish a successful physical charging session. The current tests use synthetic data and mocked transports; see [validation](VALIDATION.md).

## Meter and energy sources

| Equipment / source | Route | Current project scope | Qualification focus |
|---|---|---|---|
| Sigenergy ESS | Sigenergy Local Modbus → Home Assistant → configured sensor mappings | Generic HA readings; no direct Sigenergy register driver | Firmware, enabled Modbus, units, import/export sign, real source freshness |
| Shelly Pro 3EM | Local `EM.GetStatus` RPC | Direct read adapter and normalized grid readings | Exact device generation, CT placement/direction, phase mapping, error flags |
| Other inverters / local meters | Their HA integration → configured sensor mappings | Generic HA reading contract | Confirm sensor actually measures the grid connection, not inverter output |
| Wattwatchers | Authorised cloud REST API | Documented candidate; no Wattwatchers adapter yet | API entitlement, devices, latency, quotas and commercial terms |
| Energex customer meter history | Requested CSV / NEM12 file | Analysis source candidate; no importer yet | Interval convention, substitutions, tariff alignment, customer authority |

Choose one authoritative grid measurement for a site and use a second source for reconciliation. Do not add two measurements of the same wire together. See [metering](METERING.md) for the distinction between live control data and billing history.

## Charger candidates

| Candidate | Evidence available | Conditions before supporting it |
|---|---|---|
| **Fronius Wattpilot Flex Home 11 C6 / 22 C6, Australian specification** | Australian data sheet specifies OCPP 1.6 J. evcc has a Wattpilot OCPP adapter, including phase switching and RFID support | Exact SKU/firmware, current limits, OCPP server access, sponsor token, energy measurement and restart tests; validate the Flex variant against the upstream adapter |
| **Wallbox Pulsar Plus, OCPP-enabled variant** | Wallbox documents OCPP-specific part-number variants; evcc has firmware-specific adapters | Confirm Australian part number and firmware. Upstream documents incomplete meter values and connection recovery limitations. Treat this as a later qualification candidate |
| **Another charger listed by evcc** | Upstream driver is a starting point | Complete the same tests; an OCPP logo alone does not prove required commands, measurements or recovery behavior |
| **Tesla Wall Connector** | Home Assistant's standard integration exposes monitoring sensors | Keep the Tesla-car BLE path separate. That path does not become a general BYD charger-control method |

Fronius source: [Australian Flex Home data sheet](https://www.fronius.com/-/media/australia/se/downloads/se_ds_fonius_wattpilot_flex_home_en_aus_en-english.pdf), [evcc Wattpilot driver](https://docs.evcc.io/en/chargers/fronius-wattpilot-ocpp/). Wallbox source: [OCPP activation guide](https://support.wallbox.com/wp-content/uploads/2021/02/EN_OCPP_ACTIVATION_GUIDE.pdf), [evcc Pulsar Plus FW 5.x driver and limitations](https://docs.evcc.io/en/chargers/wallbox-pulsar-plus-fw-5-x/). Tesla source: [HA Wall Connector integration](https://www.home-assistant.io/integrations/tesla_wall_connector/).

The Fronius names also show why the full model matters: the Australian data sheet gives the 11 C6 a single-phase maximum of 3.68 kW and the 22 C6 a single-phase maximum of 7.36 kW. A model's three-phase nameplate rating is not its single-phase charging power. Check the car's AC charger and the installed circuit as well.

## Vehicles: useful even without an API

A compatible AC vehicle can use charger-managed solar charging without a manufacturer account. evcc explicitly supports guest and generic offline vehicles. Start with “use surplus” or an energy amount. Battery percentage is an optional improvement. [evcc vehicle documentation](https://docs.evcc.io/en/features/vehicle/)

| Vehicle profile | Suitable request | What remains unknown |
|---|---|---|
| BYD / MG / Kia / Hyundai / Tesla / other compatible car, no telemetry | Add a chosen amount of charger-delivered energy, or use surplus | Absolute battery percentage and remaining usable capacity |
| Vehicle with a fresh, correctly identified SOC source | Reach a requested battery percentage using a documented usable capacity and efficiency assumption | Exact final SOC remains subject to measurement, losses and vehicle limits |
| Guest or ambiguous vehicle | Conservative guest limits and explicit energy request | Which stored car profile applies |

These are **capability profiles**, not a claim that every model has been tested. The car must accept the connector, supply phases, advertised current and repeated pause/resume behavior of the selected charger.

Ordinary Type 2 AC charging does not generally provide the battery percentage through the charging cable. Some combinations add ISO 15118 capabilities; record evidence for the specific pair before relying on that path. An OCPP station identifier identifies the charger. A connector number identifies an outlet. Neither should be treated as the vehicle's VIN. An RFID identifier can be mapped to a vehicle only after the owner establishes the association. [evcc generic OCPP configuration](https://docs.evcc.io/en/chargers/ocpp-1-6j-compatible/), [vehicle assignment](https://docs.evcc.io/en/features/vehicle/)

For **BYD**, the community [BYD Vehicle integration](https://github.com/jkaberg/hass-byd-vehicle) provides a candidate HA route. Its data is cloud-polled; country/account selection matters and frequent polling may increase standby drain. Our BYD profile consumes explicitly mapped HA telemetry. We have not tested an Australian model/account, implemented BYD authentication, or enabled vehicle commands. No control PIN is needed for our read-only use. Verify SOC against the car, age while asleep, plug state and behavior after a cloud login expires before using it for a percentage target.

## A repeatable qualification record

Use a private record for each tested combination. Publish an anonymised capability result only after the owner approves its content.

1. Record charger SKU, region, firmware, evcc version and driver, meter model, car model/year/firmware, host and network layout.
2. Identify the physical grid measurement and charger circuit. Record signed grid power, active phases, commissioned limits and any separate load-management equipment.
3. Test one ordinary charge, current adjustment, pause and restart. Confirm measured current and energy, not only API acknowledgements.
4. Test unplug/replug, an asleep car, a guest car, wrong vehicle assignment and two cars sharing a charge point. Revoke percentage-based automation when identification is ambiguous.
5. Test cloud loss, LAN loss, frozen telemetry, evcc restart and host power loss. Record the actual charger behavior and the owner's recovery procedure.
6. Confirm energy counters across a restart and new session, SOC rounding, charging losses and the vehicle's own charge limit. Check a deadline the system can meet and one it cannot.
7. Run shadow planning before enabling a supervised handoff. An unattended service needs the additional lifecycle controls described in [the design](MULTIBRAND_DESIGN.md).

The first commercial profile should cover one charger family, one metering route and a small number of observed vehicle combinations. New firmware is a change to qualify, not a reason to silently extend the support badge.

## Open source and installation economics

evcc's source is [MIT licensed](https://github.com/evcc-io/evcc/blob/master/LICENSE). Preserve notices when distributing it. Its operational sponsor-token requirements are a separate part of the installation: both charger candidates above currently require tokens. The upstream offers recurring and one-time options and installer bundles; tokens purchased for customer installations must not be resold separately. Quote the current arrangement explicitly and give the owner the relevant entitlement and renewal information. [evcc sponsorship](https://docs.evcc.io/en/sponsorship/)

Do not promise “no ongoing costs” merely because Solar Playbook is MIT licensed. Itemise charger entitlement, cloud vehicle/API charges, weather rights, optional AI usage and optional support. A subscription-free installation can use appropriate upstream entitlements and local data, but must be checked against the chosen equipment. The service business should sell commissioning, reliability and support, with independently owned customer accounts and a documented handover.

Sources reviewed **13 October 2026**. These are a shortlist and an evidence standard, not purchasing commitments.
