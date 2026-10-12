# Device and Apple Home integrations

These procedures are independent of the host hardware. Follow the read-only stage before enabling any external equipment control.

## Sigenergy integration

Use the installation instructions in [Sigenergy Local Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus). Record the integration commit/release, HA version and inverter firmware. Begin in its read-only mode.

Ask the installer to enable the supported local Modbus interface and confirm network access during commissioning. Modbus is a communications protocol, not necessarily an extra box. If the installer leaves it disabled, installation of the HA integration alone cannot turn an unreachable interface into a working feed. Check the permitted enablement process with the installer/vendor. Do not bypass installer credentials or substitute guessed settings.

Compare PV, battery SOC, battery power, grid power and house load against the native app and a real load change. Establish the sign convention for import/export and charge/discharge. Record the exact entity IDs and units. HA reporting freshness is not proof of fresh device data: inspect an actual device poll/heartbeat too.

## Tesla BLE link

Follow the current [ESPHome Tesla BLE installation guide](https://github.com/yoziru/esphome-tesla-ble) for the **exact board**. The generic ESP32 package is not interchangeable with C3/S3 variants. Flashing, encryption and key provisioning should follow the pinned upstream instructions.

Place the board near the parked car, with reliable Wi-Fi and power. Pair it through the Tesla's supported key process with the owner physically present. Prefer the charging-manager role where supported and adequate. Keep VIN, vehicle key material, Wi-Fi passwords and ESPHome API/OTA secrets out of Git. Test wake, state readout and charging capabilities separately.

The path is HA → Wi-Fi → ESP32 → authenticated Bluetooth → car. The Wall Connector continues to supply AC subject to its electrical limits. Do not open or modify its electronics to build this integration.

This alpha does not issue BLE commands. Once the future actuator is implemented, verify actual current and charge state after each command; a successful HTTP call to HA is only an acknowledgement.

## Apple Home

Home Assistant's [HomeKit Bridge integration](https://www.home-assistant.io/integrations/homekit/) is software running inside HA. Add it under Devices & Services, select an explicit allowlist of useful entities and pair its code in Apple Home. Avoid exposing all entities by default.

`integrations/home_assistant/solar_playbook.yaml` supplies request helpers and an example allowlist. Merge configuration with an existing setup rather than creating duplicate HomeKit bridges. The helpers demonstrate the future interface; they do not operate equipment in v0.1. Target percentage and departure date/time stay on the HA dashboard initially because HomeKit does not have a native general-purpose energy-scheduling form.

For remote Apple Home access and Apple-side automations, configure a supported HomePod/Apple TV home hub. It is not a replacement for HA or the ESP32. The basic energy decision loop can remain local independently of remote Apple access.

## First read-only check

Create a suitable HA token through your own HA account and put it in the `HA_TOKEN` environment variable without sharing it. The alpha reads one configured entity at a time and never calls HA services. HA tokens can carry significant authority even when our client only performs reads; protect and revoke them accordingly.

Record successful reads, firmware versions and site limits in a private commissioning sheet. Do not upload that sheet or real telemetry to the public repository without reviewing and anonymising it.
