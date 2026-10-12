# Evidence register

Checked 12 October 2026. These sources establish interface/installation facts and licensing boundaries. The architecture, business hypotheses and synthetic economics are this project's own proposals, not vendor endorsements. Recheck current firmware, API models, prices and terms at commissioning.

| Topic | Primary source | What it supports |
|---|---|---|
| Free versus paid weather products | [BoM data services](https://www.bom.gov.au/resources/data-services) | Mixed free/paid product access; commercial-use distinction |
| Default anonymous feed terms | [BoM FTP catalogue](https://www.bom.gov.au/catalogue/anon-ftp.shtml) | Personal/internal use versus supply/commercial use |
| Forecast product structure | [BoM feeds and XML schemas](https://www.bom.gov.au/catalogue/data-feeds.shtml) | Documented XML products, availability/support limits |
| Roof-specific forecast option | [Solcast hobbyist docs](https://docs.solcast.com.au/docs/section/rooftop-sites-hobbyist) | Personal account features, quota and roof-site limits |
| Solar feed rights | [Solcast free offering](https://solcast.com/free-rooftop-solar-forecasting) | Personal/non-commercial conditions |
| Alternative hosted weather API | [Open-Meteo pricing](https://open-meteo.com/en/pricing) | Hosted commercial-use plans distinct from free use |
| Irradiance-to-PV modelling | [pvlib ModelChain](https://pvlib-python.readthedocs.io/en/stable/user_guide/modeling_topics/modelchain.html) | A possible future physical PV model |
| Raspberry Pi host | [HA Pi installation](https://www.home-assistant.io/installation/raspberrypi/) | Supported Pi models and starting hardware guidance |
| Apple silicon host | [HA macOS installation](https://www.home-assistant.io/installation/macos/) | ARM image/virtualisation guidance |
| Apple interface | [HA HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/) | Software bridge, supported entities and networking |
| HA API | [HA REST API](https://developers.home-assistant.io/docs/api/rest/) | State reads and authentication; state writes are not device service calls |
| Appliance packaging | [HA app configuration](https://developers.home-assistant.io/docs/apps/configuration/) | Future managed application packaging |
| Sigenergy telemetry | [Local Modbus integration](https://github.com/TypQxQ/Sigenergy-Local-Modbus) | Community integration, firmware/config prerequisites and licence |
| Tesla local link | [ESPHome Tesla BLE](https://github.com/yoziru/esphome-tesla-ble) | Supported boards, authenticated pairing and capabilities |
| Tesla protocol reference | [Tesla vehicle-command](https://github.com/teslamotors/vehicle-command) | Official command/protocol tooling; not endorsement of this project |
| Australian hybrid rating | [Sigenergy AU datasheet](https://www.sigenergy.com/uploads/au_download/1748249455362967.pdf) | Example 10 kW single-phase model ratings; verify exact ordered variant |
| Network connection context | [Energex dynamic connections for installers](https://www.energex.com.au/our-services/connections/residential-and-commercial-connections/solar-connections-and-other-technologies/dynamic-connections-for-energy-exports/dynamic-connections-for-installers) | Approved connection limits are a commissioning input |
| Mathematical scheduling alternative | [EMHASS documentation](https://emhass.readthedocs.io/en/latest/) | Existing forecasting/optimisation tool for HA |
| EV automation alternative | [evcc documentation](https://docs.evcc.io/en/) | Existing EV, solar and tariff orchestration |
| Predbat terms | [Predbat documentation](https://springfall2008.github.io/batpred/) | Current licence/support boundary |
| Optional local inference | [Ollama macOS](https://docs.ollama.com/macos), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs) | Optional native host and JSON request shape |
| OpenAI adapter | [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) | Responses API schema output |
| Claude adapter | [Messages API](https://platform.claude.com/docs/en/api/messages/create) | Message and tool-output envelopes |
| Compatible provider example | [DeepSeek API](https://api-docs.deepseek.com/), [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) | Explicit endpoint/model compatibility to verify |
| Paid service obligations | [ACCC guarantees](https://www.accc.gov.au/consumers/buying-products-and-services/consumer-rights-and-guarantees) | Consumer service obligations |
| Household data | [OAIC small business](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/small-business) | Privacy applicability and exceptions |
| Electrical work | [Queensland licensing](https://www.worksafe.qld.gov.au/licensing-and-registrations/electrical-licences/electrical-contactor-licences) | Contractor licensing requirements |

The supplied example is not a verified description of a particular installation, an electricity-plan quote, an API price comparison or a financial return estimate. Live physical and cloud-provider validation remain separate milestones.

## Multi-brand extension: checked 13 October 2026

| Topic | Primary source | What was checked |
|---|---|---|
| Shelly meter RPC | [EM component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/EM/) | `EM.GetStatus`, total active power in W, errors; no sample timestamp in this response |
| HA timestamp semantics | [State-reported timestamp](https://developers.home-assistant.io/blog/2024/03/20/state_reported_timestamp/) | A state report is not proof of a fresh upstream hardware sample |
| evcc pinned API | [0.317.1 API](https://github.com/evcc-io/evcc/blob/0.317.1/server/openapi.yaml), [state](https://github.com/evcc-io/evcc/blob/0.317.1/server/openapi.state.yaml) | Mode endpoint, 1-based indices, current Smart mode and receipt boundaries |
| Device and commercial evidence | [Compatibility register](COMPATIBILITY.md), [metering register](METERING.md) | Direct links for BYD, Fronius, Wallbox, sponsor terms, utility data and future RTD framework |

No commercial weather/meter API account, real household data or vehicle account was used for these tests. The API contract tests use synthetic payloads and fake transports.
