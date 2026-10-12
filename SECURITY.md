# Security

Version 0.2 adds read-only meter and vehicle adapters, plus an explicit attended evcc mode handoff. Planning, demos, meter reads and vehicle reads never write equipment. Only `charge-mode --apply --attended` can request a persistent evcc mode change, after configured commissioning gates; preview is the default. AI has no route into that handoff. Keep HA/evcc/API credentials in environment variables and private configuration, not the repository or issue tracker.

A controller response proves controller contact, not fresh physical telemetry. Mode read-back confirms evcc state only. Mode changes can persist after this process exits, and concurrent manual actions can race a handoff. There is no unattended daemon, watchdog or automatic rollback in this release. An unknown write outcome must be inspected in evcc before any new request; the client never retries it automatically. The configurable request window limits the preflight-to-POST delay, not the lifetime of the hardware setting.

Local adapters refuse redirects. Their configuration and the optional injected test transport are trusted inputs, not an internet-facing API. Do not accept untrusted remote configuration files. This release does not provide multi-tenant isolation, remote user authentication, or a secrets vault. Charger, meter and inverter firmware protections and electrical limits remain independently commissioned.

Do not expose Modbus, OCPP, evcc, ESPHome management, HA or an unauthenticated local model directly to the internet. Use supported authenticated access methods and obtain owner consent for remote support.

Before reporting a problem, remove credentials, VINs, IP topology, precise location and private telemetry. If a key may have leaked, revoke/rotate it through the relevant owner account. Use GitHub private vulnerability reporting if enabled on the repository; otherwise report the general issue without exploit details or secrets and ask the maintainer for a private channel.

Commercial use needs its own support, update and incident-response policy. An MIT licence does not certify electrical safety, hardware compatibility or API/data-provider rights.
