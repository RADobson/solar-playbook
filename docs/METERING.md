# Meter data that the system can trust

For solar charging, the useful question is “what is crossing the home's grid connection now?” A meter or inverter integration that answers that question promptly can support the local controller. The electricity retailer's billing history answers a different question: “what was consumed over past intervals?” Both are valuable, with different jobs.

## The first metering route

For a Sigenergy home, first verify the existing grid-flow measurement exposed through Home Assistant. If it is sufficient, no additional monitor is needed for the planning prototype. For another home, the same HA sensor contract or the direct Shelly Pro 3EM reader provides a portable route. Use a separate appropriately installed monitor when the required measurement is missing or independently commissioned load management requires it.

| Source | Data path | Intended use | Implemented here |
|---|---|---|---|
| Local inverter / grid meter | Device → HA sensor → Solar Playbook | Read-only planning, reconciliation and shadow checks | Configurable HA measurement adapter |
| Shelly Pro 3EM | LAN HTTP RPC → Solar Playbook | Read-only total grid power | `EM.GetStatus` reader / normalisation; phase currents are not exposed by this adapter |
| Wattwatchers | Vendor device → authorised cloud API | Monitoring, analysis; control suitability must be measured | No direct adapter |
| Energex meter-history request | Delivered CSV / NEM12 | Load profiles and comparison with bills | No importer |
| Future NEM real-time meter access | Meter/provider interface still subject to rollout | Potential future source | No adapter or present-day assumption |

The implementation is a set of readers and validators. It is not a continuous meter service, a certified meter, a replacement for a billing meter, or a commissioned load-protection device. Every current `MeterReading` remains `control_eligible: false`; a fresh response never authorises a charger action.

## Local data sources

**Sigenergy:** the community integration exposes plant grid flows via local Modbus and starts read-only. Its current notes warn that grid-side phase voltage/current details are not available through a stable documented register set; some previously added sensors were removed. Inverter phase readings must not be relabelled as grid-service measurements. Confirm the exact entities and supported firmware during commissioning. [Sigenergy Local Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus)

**Shelly Pro 3EM:** the documented RPC request is `GET /rpc/EM.GetStatus?id=0`. The response contains signed total active power and optional phase current, voltage and active-power values, plus errors. This is the Pro device's RPC interface; older Shelly 3EM devices use a different API. `EM.GetStatus` does not provide a trustworthy measurement timestamp in the response. Our received-at time therefore proves when the response arrived, not when its internal ADC last sampled. [Shelly EM component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/EM/)

A local reader does not require a cloud subscription. It still requires a suitably installed device, working networking and tested authentication. Keep the monitor's configuration and calibration controls outside Solar Playbook. A device or HA token may have broader authority than this reader uses; protect it accordingly.

**Wattwatchers:** the documented `short-energy` endpoint supplies short-interval energy data, typically 30 seconds. API keys are issued by Wattwatchers and scoped to devices and permissions. Treat API access, hardware, connectivity and service terms as a supplier integration to arrange, not as a free public API for any electricity meter. Converting an interval's energy to average power does not create an instantaneous measurement. [Endpoints](https://docs.wattwatchers.com.au/api/v3/endpoints.html), [authentication](https://docs.wattwatchers.com.au/api/v3/auth.html)

## Utility history and future access

Energex currently documents requested historical customer data: interval-meter data is supplied in a monthly detailed CSV, with up to two years available for an eligible account holder or authorised representative. This is useful for sizing, baseline consumption and savings analysis. It is not the feed to use for responding to a passing cloud. The current project neither requests private meter data nor parses that file. [Energex customer metering data](https://www.energex.com.au/our-services/metering/accessing-your-metering-data)

AEMO describes **30 November 2028** as the commencement for consumer access to real-time smart-meter data under the new framework. Customer-appointed representatives must meet the framework's consent and accreditation requirements. This is a future integration opportunity, not evidence that an arbitrary Australian smart meter has an open HTTP endpoint today. [AEMO Real-Time Data](https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/real-time-data)

## Normalisation contract

At the adapter boundary, use the following semantics. An explicit configuration maps the source into them; auto-detecting a sign from a few readings is insufficient.

| Concept | Required interpretation |
|---|---|
| Grid active power | Normalized as `grid_power_kw` in kW; **positive = import**, **negative = export**. Source W/kW is configured explicitly |
| Energy | kWh and a named measurement boundary, for example AC delivered by the charger |
| Phase current | Future extension: amps per identified physical phase. Current adapter only carries configured phase-count metadata and cannot establish phase headroom |
| Observation time | An aware timestamp for a measurement or source update, when available |
| Receipt time | When this adapter received the response; keep its distinction from observation time |
| Source | Adapter, timestamp basis and configured entity/device identity; retain the private configuration beside a diagnostic result |
| Quality | Missing, unavailable, malformed, stale or unsupported values are errors/unknowns, never zero |

A reading is suitable for a report only when its limitations are visible. A reading is suitable for control only when the active controller's source-health checks, freshness limits and site commissioning permit it. A recent HA `last_updated` value can be useful evidence but cannot by itself prove that a frozen upstream device is measuring again. Unchanged power may be a real steady load; staleness needs a heartbeat or other source evidence rather than “the value did not move.”

Finite numeric parsing is necessary: reject `NaN`, infinity, booleans presented as numbers and invalid units. Reject implausible future timestamps and assess age against the caller's aware clock. Record tolerances as configuration rather than quietly inferring them from the weather. The concrete validation fields and command examples are in [installation](INSTALL.md) and the module tests.

## A practical first measurement check

1. Locate the measured conductor and record whether the source covers the whole site, an inverter or one subcircuit. Confirm CT direction and phase association with the installer.
2. At night, switch on a known load and confirm increased positive grid import. In daylight, compare export against the native app or meter. Do not alter electrical wiring to perform the software test.
3. Compare at matching times. A 30-second average and a live power value can differ legitimately; their integrated energy should converge over an appropriate interval.
4. Verify stale/unavailable handling by disconnecting the data source. The reader should fail visibly. Separately test evcc's meter-loss behavior: our read-only result is not wired into a continuous charging interlock.
5. Reconcile cumulative energy over several days, accounting for counter resets, time zones and daylight-saving rules. Do not integrate over missing intervals as if power were zero.

This is measurement validation, not an electrical commissioning certificate. See [commissioning](COMMISSIONING.md) for the wider process.

## Two traps that affect useful automation

**Total power is not phase headroom.** A three-phase site can have one heavily loaded phase while net total import looks modest. This release's simulator is single-phase. It does not certify multi-phase load management. The selected charger/controller and installed protections must enforce actual circuit and phase limits independently of a forecast or language model.

**A zero feed-in payment is different from a zero-export setting.** A household may receive no money for exported energy while still being allowed to export. That exported surplus is observable. A site actively held at zero export may instead curtail generation, so an export-following controller cannot discover the unused solar simply by waiting for a negative grid reading. evcc explicitly documents that boundary. Qualify a supported curtailment-aware approach before promising surplus capture on such a site. [evcc solar charging](https://docs.evcc.io/en/features/solar-charging/)

Sources reviewed **13 October 2026**. Local meter readings remain private household data: retain only the history needed for support and analysis, and redact device IDs, addresses and detailed occupancy patterns before sharing a diagnostic file.
