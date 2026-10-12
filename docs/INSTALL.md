# Hardware-neutral installation

## Recommended starting point

Find the existing 4 GB Raspberry Pi and identify its exact model. If it is a supported Pi 4/5 with reliable power and storage, it is a sensible candidate for Home Assistant and a lightweight scheduler that calls an external AI API. Home Assistant's current Pi guide recommends Pi 4/5 with at least 2 GB and strongly prefers Ethernet. The complete Solar Playbook stack still needs its own commissioning benchmark. [Official Pi installation](https://www.home-assistant.io/installation/raspberrypi/).

No GPU or local language model is required. The device performs ordinary network requests and small scheduling calculations. The existing Mac remains useful for development, but does not need to become a permanent appliance.

## Separate the three decisions

| Decision | Default direction | What can change independently |
|---|---|---|
| Host | Suitable existing always-on device | Pi, small PC, server/VM, Mac |
| Home automation | Home Assistant | Physical integration adapters and exposed UI |
| Optional AI | Explicit external API provider | OpenAI, Claude, compatible provider, local Ollama, or none |

The Python core targets 3.11+ and has no runtime dependencies. ARM64 and x86-64 are intended deployment architectures; the source has been exercised on the development Mac, not physically certified on every target. The Docker recipe is supplied, but no multi-architecture image has yet been built/published in this release.

## Development/demo path today

On a machine with Python 3.11+:

```sh
python3 -m solar_playbook device-demo --out out/demo
python3 -m unittest discover -s tests -v
```

Open `out/demo/report.html`. The file needs no server. On Linux, a supported OS running Home Assistant Container can also run the planner as a separate Python process/container. Follow Home Assistant's current [installation choices](https://www.home-assistant.io/installation/) for host requirements.

Optional container build on a Docker-capable host:

```sh
docker build -t solar-playbook:local .
mkdir -p out/container
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD/out/container:/out" \
  solar-playbook:local demo --out /out
```

This is a one-shot simulation job, not a live controller. No privileged mode or device access is required. The output-directory ownership must permit the chosen container user to write it. Keep private configuration and API keys outside the image.

## Appliance path to complete before selling installations

Home Assistant OS is the preferred appliance experience for many households. It is not a general-purpose Linux installation into which users should run arbitrary `pip install` commands. Package Solar Playbook as a Home Assistant app/add-on with persistent config, health reporting, constrained permissions and ARM64/x86-64 images. The [official app configuration guide](https://developers.home-assistant.io/docs/apps/configuration/) describes the packaging surface.

That app is **not included as a working installable package in v0.2**. It depends on the real-site daemon, forecast refresh, control ownership and watchdog milestones. Until then, use the simulator and read-only adapters on an ordinary Python host; the optional evcc handoff is for attended commissioning. Do not sell the CLI as a completed unattended appliance.

## BYO device acceptance

Require a supported OS/architecture, adequate free memory/storage, reliable power, a stable network address, LAN reachability, automatic recovery policy, backups and an owner willing to keep the host available. Check USB/storage health and the actual workload already running on the device.

Reject or separately quote hosts that sleep unpredictably, run an unsupported OS, share unstable storage, or have inaccessible owner/admin accounts. Customer-supplied hardware does not mean unlimited troubleshooting of unrelated software. Put the responsibility for hardware replacement and host uptime in the service scope.

For installer-supplied equipment, qualify a small set of commercially available devices. Include a known power supply, appropriate storage, case/cooling, serial/inventory record, recovery media and a tested restore path. Prefer good storage and recovery over unnecessary CPU power. No custom PCB is needed for the first service offering.

## Common components

Meter, optional vehicle and evcc charger adapters are independent of host choice. The Tesla-specific ESP32 link is one optional path; BYD and other brands can charge through a qualified smart charger without it. Follow [the shared integration guide](INTEGRATIONS.md) for device setup and [the Mac appendix](INSTALL_MAC.md) only if you choose that host.

## Reliability target

Internet loss removes fresh cloud forecasts/AI, but the local automation layer must continue with cached inputs only while valid and a documented fallback after expiry. A host outage is different: native equipment settings become the fallback. A phone, tablet or laptop that regularly leaves home should be a user interface, not the control host.

## Multi-brand setup

Run the offline example first, then follow [device integrations](INTEGRATIONS.md), [metering](METERING.md), and the [compatibility matrix](COMPATIBILITY.md). Copy examples into the ignored `private/` directory before substituting real hostnames, identities, phase counts and site limits. A placeholder is not an automatically discovered device.

Install/configure evcc separately from its official instructions. The source collector does not install, execute or provision it. Pin and commission the adapter contract version (0.317.1 for this release); selected charger integrations may need a sponsor entitlement. Home Assistant and evcc must not both act as charger writers. Configure the grid meter, physical limits and native recovery behavior within the selected equipment and evcc before enabling any Solar Playbook handoff.
