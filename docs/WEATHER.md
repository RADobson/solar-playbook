# Weather, solar forecasts and BoM

## Yes, there are free BoM feeds

BoM offers forecast, warning and observation products through its anonymous service. The published default terms allow personal/internal use and restrict commercial use or supplying the material to others. Richer forecast grids, radar, satellite and supported registered feeds can be paid products. Some individual datasets have different licences: check the selected product rather than assuming one rule for all BoM data. [BoM data services](https://www.bom.gov.au/resources/data-services), [anonymous FTP terms](https://www.bom.gov.au/catalogue/anon-ftp.shtml).

For an individual home, a free BoM weather feed is a reasonable starting point. A public code repository can contain a parser and synthetic tests without redistributing real forecast files. A future commercial service needs permission for its actual data use. Whether paid installation of a homeowner's personal account is acceptable should be confirmed with the provider; it is different from centrally reselling forecasts to a fleet.

## Weather context and solar power are different inputs

“Cloudy, showers likely” helps explain uncertainty and may justify a conservative plan. It does not identify the half-hour when clouds will cover a specific roof, nor how many kWh each roof orientation will deliver. Rain probability is not the fraction of sunlight lost. Radar shows precipitation, not every cloud that affects PV.

The numerical planner needs **average available panel DC power by interval**. A roof model needs position, orientation, tilt, shading, installed DC capacity and losses, with an irradiance forecast as input. [pvlib ModelChain](https://pvlib-python.readthedocs.io/en/stable/user_guide/modeling_topics/modelchain.html) is a possible future modelling component. A provider's already-inverter-clipped AC forecast cannot simply be renamed DC; doing that loses the energy the hybrid could have sent to its battery.

## A practical sequence

1. Start with BoM context plus measured local telemetry and a native cheap-window charging fallback.
2. Add a suitable roof-specific PV forecast. Solcast's personal hobbyist option is a candidate if the user accepts its terms. Its current published limits include two roof sites and ten calls per day; commercial use needs separate arrangements. Multiple roof requests can consume separate calls. [Solcast hobbyist documentation](https://docs.solcast.com.au/docs/section/rooftop-sites-hobbyist), [terms of the free offering](https://solcast.com/free-rooftop-solar-forecasting).
3. Compare forecast versus production for several weeks. Separate systematic shading/orientation error from temporary cloud error. Calibrate on training days and evaluate on held-out days.
4. For an installer fleet, price a licensed weather/solar provider or a suitable self-hosted model. Keep the adapter boundary unchanged. Open source forecast software does not make hosting or upstream data rights free. Open-Meteo's hosted free tier, for example, currently limits commercial use. [Open-Meteo pricing](https://open-meteo.com/en/pricing).

## Implemented BoM adapter

`solar_playbook.forecast.parse_bom_xml` reads a **local XML file** and selects the exact area AAC. It extracts the issue timestamp, period boundaries and named weather elements. It rejects oversized documents, DTDs/entities, missing area codes and invalid periods. `weather_is_fresh` checks issue age and current coverage.

The parser targets BoM's documented XML product structure. Tests use invented content shaped like that structure. It has not yet been commissioned against a live, selected Queensland product. It deliberately does not guess an area code or scrape an undocumented mobile-app API.

Follow the official [feed catalogue and XML schema links](https://www.bom.gov.au/catalogue/data-feeds.shtml) to choose a product and area. Download it for your authorised use into `private/` and run:

```sh
python3 -m solar_playbook bom private/forecast.xml --area YOUR_AREA_AAC
```

The automatic downloader is a later adapter milestone. Its required contract is bounded request time, product-specific polling interval, conditional requests where supported, exponential backoff, size limits, atomic cache replacement and visible issue time. Anonymous FTP is not an authenticated warning channel; don't turn an unauthenticated weather message into an emergency equipment command.

## Forecast contract

| Field | Meaning |
|---|---|
| `generated_at` | Provider issue time, not the time a cached file was reread |
| `slots[].start` | Aware timestamp; Queensland examples use UTC+10 |
| `slot_minutes` | Constant interval duration: 15, 30 or 60 |
| `slots[].pv_dc_kw` | Interval-average available panel DC power before shared-inverter clipping |
| `slots[].home_kw` | Base household AC demand excluding the scheduled EV |
| `slots[].import_aud_per_kwh` | Marginal import price for that interval, including the site's applicable taxes |
| `slots[].export_aud_per_kwh` | Export price; zero is valid |

Provider adapters must document whether their timestamp denotes period start or end and whether power is AC or DC. Reject missing intervals, unknown units and non-finite values. Do not fill a missing forecast with sunny-day assumptions.

## How uncertainty should affect the playbook

Replan at moderate intervals using local observations; retain a charging deadline buffer. Evaluate a central and conservative lower-generation forecast once probabilistic inputs are added. Providers can define percentile conventions differently, so normalise the meaning rather than relying on a label such as P90.

On a cloudy morning, a cheap daytime import window may make charging then preferable to gambling on late sunshine. On a bright day, shifting the EV into surplus can reduce clipping. When the car is away, the correct action may be to fill the home battery and accept zero-value exports. No model can use car storage when the car is not plugged in.

If forecasts fail, notify and use a precommissioned native schedule. If local telemetry fails, withdraw automation eligibility. A cached forecast can keep a dashboard useful without being recent enough to authorise control. Storm-related reserve changes should be deterministic and owner-configured; this alpha does not implement emergency-warning automation.

## Provider selection checklist

Assess local forecast skill, irradiance/PV fields, issue frequency, latency, historical access, percentiles, rate limits, commercial rights, outage behaviour and total cost. A “high quality” national forecast can still be poorly calibrated to a shaded roof. Measure useful planning accuracy at the home before paying for more granular data.
