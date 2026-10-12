# Installation on an Apple silicon Mac mini

This is an optional host-specific appendix. The primary design is now hardware neutral with optional cloud AI; start with [the main installation guide](INSTALL.md). A Mac or local model is not required.

## First, run the demo

Use Python 3.11+ and the commands in the README. Running `python3 -m solar_playbook` directly from the checkout does not need `pip install`. This is the simplest way to assess the project before setting up a VM or buying hardware.

## Hardware to gather

| Component | Why | Purchase status |
|---|---|---|
| Existing M4 Mac mini, 16 GB | HA VM, planner and optional native Ollama | Sufficient starting platform; no new Pi required |
| Ethernet connection | Reliable host connection and easier network diagnosis | Use if available |
| Supported ESP32 board, USB supply/cable, suitable enclosure | Wi-Fi to local Tesla BLE link | Choose an exact board supported by upstream firmware |
| Existing HomePod mini or Apple TV | Apple home hub | Recover an existing device before purchasing another |
| Router that permits local device discovery | HA, HomeKit, ESPHome and inverter communication | Verify LAN/VLAN/firewall behaviour |
| UPS for host and network gear | Optional graceful continuity | Size after measuring power; not required for the simulator |
| Sigenergy inverter/battery and separately installed Wall Connector | Real energy equipment | Configured by the responsible installer |

No hardware prices are quoted here. Check local availability, authentic board variants, power supplies and installation cost when ordering. The old iPad can be a dashboard if its supported OS/browser can run the interface; do not assume it can act as a home hub for the current Apple Home architecture.

## Home Assistant virtual machine

Use the current [official macOS installation guide](https://www.home-assistant.io/installation/macos/). Download the **Apple silicon ARM** image, not the Intel x86 image. The guide currently documents VirtualBox and also lists UTM as an alternative. Follow its current firmware/storage configuration rather than a generic Linux VM tutorial.

Start with 2 virtual CPUs, 4 GB RAM and a 64 GB virtual disk. Use bridged networking, confirm HA has its own reachable LAN address, then finish onboarding at its local web UI. Reserve its DHCP address. Back up the VM and HA configuration before installing community integrations.

Do not put HA on an isolated NAT network and assume HomeKit/mDNS or inverter discovery will cross it automatically. If you use IoT VLANs, allow the specific required paths and test discovery. Do not expose HA, Modbus port 502 or ESPHome management directly to the internet.

For Sigenergy, Tesla BLE, HomeKit and read-only API setup, follow [the shared integration guide](INTEGRATIONS.md).

## Optional Ollama

Install the official macOS application from [Ollama](https://docs.ollama.com/macos). Native installation uses Apple silicon acceleration. Start with `qwen3:4b`, whose published quantised download is approximately 2.5 GB; working memory is larger and varies with context and use. [Model listing](https://ollama.com/library/qwen3:4b).

The implemented adapter calls only `127.0.0.1:11434`, requests bounded structured JSON and times out after 20 seconds. Keep the Ollama port local. If the model times out or returns invalid output, the report uses a deterministic explanation. The model is optional for every stage of basic scheduling.

## Keep the Mac dependable

Choose a host policy that keeps it awake while required, but keep disk encryption and authentication protections enabled. Test the behaviour after a normal reboot, a power interruption, a macOS update and a logged-out state. FileVault may require an owner login before a VM/service can resume; document that dependency.

This release does not install a launch agent, daemon or automatic login. A later supervised service must start only after the network and HA are ready, use a single-instance lock, expose a health heartbeat and stop cleanly. A timer that restarts a crashed script is insufficient if an earlier charge command remains active.

Back up HA, site configuration, pairing recovery instructions and version records. Encrypt backups that contain device keys. Perform a restore drill before relying on the system overnight.
