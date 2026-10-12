# Business case: installation and dependable operation

## The proposition worth testing

“Your solar, home battery and car work together, with a simple household interface and somebody who can maintain the setup.” The customer buys commissioning, reliability, documentation and support. The open source code helps establish trust and avoids trapping the household in a proprietary account.

The strongest initial customer is an owner with cross-brand equipment, an EV regularly at home during useful charging hours, a clear tariff opportunity, and frustration with manual scheduling. An installer partner gains a documented post-installation automation service and a clear escalation path. These are hypotheses to validate, not proven market demand.

The offer should still make sense without AI. If the customer only needs a native charging timer, configure it and price that smaller job fairly. The interesting commercial work lies in the exceptions: changing departure times, uncertain generation, battery/EV competition, cross-vendor control and a household that does not want to maintain Home Assistant.

## Two ways to deliver the hardware

**BYO host:** perform a fixed-scope suitability check, install on supported hardware, document what the customer must keep running, and price unusual troubleshooting separately. Allow Pi, small PC, existing HA host or a suitable VM once qualified. Hardware agnosticism expands the market; it does not eliminate the cost of supporting arbitrary old systems.

**Supplied appliance:** sell a tested commodity device with reliable storage, power supply, cooling, recovery image and inventory record. Include a replacement/repair policy. It need not be a Mac mini and should not require a GPU. Keep a small supported-device list while leaving the software architecture portable.

Offer the ESP32 bridge as a separately identified component when the supported vehicle path requires it. Keep electrical installation and any required metering with the licensed installer. A custom hardware design is unnecessary before demand and support economics are known.

## Initial service packages to test

| Offer | Concrete deliverable | Natural boundary |
|---|---|---|
| Assessment | Tariff/usage review, equipment compatibility and host suitability | No promised savings or hardware purchase commitment |
| Commissioning | Supported integrations, tested playbooks, Apple Home requests, fallback and handover | One agreed site profile; owner acceptance tests |
| Optimisation review | Compare actual operation with baseline and refine configuration | Measured report over a defined period |
| Optional maintenance | Tested updates, health checks, agreed response window and capped support scope | Explicit recurring price; core keeps working if cancelled |

Keep no-subscription ownership possible. It is reasonable to charge for future labour without charging rent for an already-installed timer. Distinguish the installation fee, hardware margin, optional support and third-party API/weather charges. “Lifetime support” without a funded reserve is not a credible promise.

BYO API keys give the household control of its provider account. An installer-managed API account can simplify setup later, but needs per-customer metering, tenant isolation, credential handling, spending controls, consent and clear offboarding. A shared secret embedded in every device image is unacceptable. Do not build a central cloud platform until the local pilot reveals a need.

## Competition and substitution

| Alternative | Why an owner might prefer it | What our service must demonstrate |
|---|---|---|
| Native inverter AI plus Tesla schedule | Already paid for; few moving parts | Meaningful extra convenience or measured savings |
| Tesla energy ecosystem | Integrated experience | Cross-brand value without making equivalent reliability claims |
| evcc | Established EV/solar/tariff automation | Why commissioning/support is worth paying for even with existing software |
| EMHASS | Existing optimisation engine | Reuse it when appropriate; avoid selling an inferior reinvention |
| Predbat | Capable battery scheduling ecosystem | Respect its current licence and supported commercial route |
| Installer's existing monitoring service | Trusted relationship and equipment knowledge | Clear responsibilities and evidence, not extra alert noise |

The durable advantage is a tested compatibility matrix, repeatable installation, excellent handover and accumulated fault/recovery knowledge. A generic prompt sent to a cheap model is easy to copy. Open source can grow referrals and external testing, but issue triage and security maintenance are real work.

## What creates value in a zero-feed-in household

Value comes from reducing **paid imports at useful times**, meeting departure requirements and reducing owner effort. Some surplus has no financial value when there is nothing useful to consume it. More battery cycling is not automatically better. A cheap daytime tariff can make a simple fixed schedule highly competitive with an elaborate weather-aware optimiser.

Measure against at least two baselines: the actual previous household behaviour and a competent native cheap-window schedule. Keep reserve/ending SOC comparable. Correct for weather, EV energy demand, occupancy and tariff changes. Avoid attributing a sunny month or a newly installed battery to the automation service.

Evidence should include departure success, total EV energy delivered, import cost, battery throughput, override frequency, host downtime, owner minutes spent, and support minutes per home. Present uncertainty and explain excluded fixed charges. Do not project one synthetic day into an annual-dollar sales claim.

## Illustrative unit economics

These are **invented ex-GST planning assumptions**, not market prices or quotes. Hardware and electrical work are separate.

| Per-site item | Assumption | Amount |
|---|---:|---:|
| Commissioning revenue | Fixed service fee | A$900 |
| Assessment, install, handover | 6 hours at A$80 internal labour cost | A$480 |
| First-year included support provision | 1.5 hours at A$80 | A$120 |
| Travel/admin allocation | Per site | A$60 |
| Acquisition/partner allocation | Per site | A$90 |
| Contribution before fixed overhead, insurance and tax | Revenue less above costs | **A$150** |

At ten delivery hours instead of six, the same job contributes **negative A$170**. At four delivery hours, it contributes A$310. One extra two-hour support visit consumes A$160. This illustrates why narrow supported profiles, remote diagnosis and scope boundaries matter more than saving a few cents on an AI call.

An optional maintenance fee must cover expected support, provider/monitoring costs, update testing, incident spikes and margin. Pay-as-needed support avoids a compulsory subscription but produces less predictable cash flow. Do not promise an unlimited service at a price built from average API cost alone.

## Installer partnership

Start with one installer and one repeatable equipment combination. Agree a division of work: electrical commissioning and vendor warranty matters remain with the responsible installer; software configuration, playbook support and data handling have named owners. Decide who receives the first call when the car is not charged.

Provide an installer intake sheet, compatibility checklist, pre-install LAN requirements, commissioning evidence pack, native fallback card and a clear referral/fee arrangement. Do not pay or assume referrals before discussing terms. The installer should not need to learn Python to explain the product.

Initially interview five installers and ten owners. Ask about failures and time spent, not just whether “AI solar sounds useful.” Test willingness to pay against a concrete scope and handover example. Then run 3–5 opt-in pilot homes with similar equipment and different daily patterns. Obtain permission before collecting or sharing identifiable household data.

## Pilot go/no-go criteria

The following are proposed targets, not achieved results:

- At least 30 days per pilot with no automation-induced critical charging failure; investigate every missed departure rather than hiding it in an average.
- Median installation/handover time within the priced allowance and support minutes within the provision.
- Owner can use pause/charge-now and restore native operation without the developer present.
- Verified recovery from host, network and provider failures; no internet-exposed device control.
- Clear measured advantage in convenience or cost over a competent native setup; owners can explain what they are paying for.
- Documented licences, forecast rights, supplier responsibilities and data-retention choices suitable for the paid offering.

Pause commercial expansion if savings are negligible and owners do not value the convenience, if every firmware revision breaks the integration, or if support exceeds margin. A smaller “set up and teach the native system” service may then be the better product.

## Responsibilities when this becomes a paid service

Agree the scope of electrical versus software work with appropriately licensed partners. Check insurance coverage for advice, remote control, cyber incidents and supplied hardware. Review vendor warranty/support conditions without asserting that any third-party integration automatically voids a warranty.

Australian consumer guarantees can apply to paid services regardless of an open source code disclaimer. Services need appropriate care/skill and suitability for the represented purpose. [ACCC consumer rights](https://www.accc.gov.au/consumers/buying-products-and-services/consumer-rights-and-guarantees).

Privacy obligations depend on the business and its practices; do not assume every small business is exempt. Household load and EV traces can reveal routines even without an address. Build minimisation, consent, security and offboarding into the product early. [OAIC small-business guidance](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/small-business).

Model/data licences, commercial API rights and software licences are separate. MIT code may be usable commercially while a linked feed has personal-only terms. The software source licence also does not grant permission to market using a vendor's trademark or claim certified compatibility.

## Tangential opportunities, in sensible order

After EV charging, hot water and other deferrable loads may offer simpler value than more complex AI. Add each only with clear comfort and electrical constraints. Fleet monitoring and installer diagnostic reports may be a stronger business than selling another consumer app. Tariff comparison can be useful, but requires current plan details and should not become unlicensed or misleading financial/savings advice.

Dynamic export, VPP integration, backup operation, demand response, bidirectional EV power and multi-tenant buildings introduce different constraints and counterparties. Keep them outside the first supported profile. Local voice explanations and richer Apple interfaces are useful only after the core charging/fallback experience is dependable.
