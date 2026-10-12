# Security

This alpha has no hardware actuator. It can read Home Assistant and, only when explicitly requested/configured, call an AI endpoint. Keep HA/API credentials in private process configuration, not the repository or issue tracker.

Do not expose Modbus, ESPHome management, HA or an unauthenticated local model directly to the internet. Use supported authenticated access methods and obtain owner consent for remote support.

Before reporting a problem, remove credentials, VINs, IP topology, precise location and private telemetry. If a key may have leaked, revoke/rotate it through the relevant owner account. Use GitHub private vulnerability reporting if enabled on the repository; otherwise report the general issue without exploit details or secrets and ask the maintainer for a private channel.

Commercial use needs its own support, update and incident-response policy. An MIT licence does not certify electrical safety, hardware compatibility or API/data-provider rights.
