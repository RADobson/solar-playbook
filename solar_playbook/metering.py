"""Read-only, portable grid power observations. No adapter can authorize control.

Positive grid_power_kw means import; negative means export. Timestamp provenance
is retained: an HA state report or HTTP receipt is not a device heartbeat.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
import re
from urllib.parse import quote, urlparse
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .model import timestamp


MAX_RESPONSE_BYTES = 100_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MeterReading:
    grid_power_kw: float
    observed_at: str
    received_at: str
    source: str
    timestamp_quality: str
    timestamp_basis: str
    phase_count: int | None
    raw_unit: str
    input_sign: str
    control_eligible: bool = field(default=False, init=False)
    hardware_write_performed: bool = field(default=False, init=False)

    def as_dict(self) -> dict:
        return asdict(self)

    def is_fresh(self, now: datetime, max_age_seconds: int = 120) -> bool:
        """Age check only; True never upgrades unverified timestamp provenance."""
        _policy(now, max_age_seconds)
        return all(0 <= (now - timestamp(value)).total_seconds() <= max_age_seconds
                   for value in (self.observed_at, self.received_at))


class NoMeterRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("meter redirects are refused")


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("meter times must be timezone-aware")
    return value


def _parse_time(value) -> datetime:
    try:
        return timestamp(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("invalid meter timestamp; use ISO time with UTC offset") from None


def _policy(now: datetime, max_age_seconds: int) -> None:
    _aware(now)
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 3600:
        raise ValueError("meter max_age_seconds must be an integer from 1 to 3600")


def _phase_count(value):
    if value is not None and (type(value) is not int or value not in (1, 2, 3)):
        raise ValueError("phase_count must be 1, 2, 3 or null")
    return value


def _power(value, unit: str, sign: str, *, numeric_string: bool = False) -> float:
    if unit not in ("W", "kW"):
        raise ValueError("meter power unit must be W or kW, not energy")
    if sign not in ("import_positive", "export_positive"):
        raise ValueError("configure the meter sign explicitly")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("meter power must be a finite number")
    if isinstance(value, str) and not numeric_string:
        raise ValueError("meter power must be a JSON number")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError("meter power must be a finite number") from None
    if not math.isfinite(number):
        raise ValueError("meter power must be a finite number")
    return number / (1000 if unit == "W" else 1) * (1 if sign == "import_positive" else -1)


def _reading(*, value, unit, sign, observed_at, received_at, now,
             max_age_seconds, source, timestamp_quality, timestamp_basis,
             phase_count, numeric_string=False) -> MeterReading:
    _policy(now, max_age_seconds)
    _aware(received_at)
    _aware(observed_at)
    if observed_at > received_at:
        raise ValueError("meter observation follows its receipt")
    result = MeterReading(
        grid_power_kw=_power(value, unit, sign, numeric_string=numeric_string),
        observed_at=observed_at.isoformat(), received_at=received_at.isoformat(),
        source=source, timestamp_quality=timestamp_quality,
        timestamp_basis=timestamp_basis, phase_count=_phase_count(phase_count),
        raw_unit=unit, input_sign=sign)
    if not result.is_fresh(now, max_age_seconds):
        raise ValueError("meter observation is stale or in the future")
    return result


def parse_shelly(payload: dict, *, received_at: datetime, now: datetime,
                 sign: str, component_id: int = 0, phase_count: int | None = None,
                 max_age_seconds: int = 120, fixture: bool = False) -> MeterReading:
    """Parse the direct HTTP EM.GetStatus response, with power measured in W.

    The RPC response has no sampling timestamp. Receipt time is explicitly
    labelled and is never treated as proof that the physical meter is healthy.
    A fixture keeps its recorded receipt instead of acquiring today's timestamp.
    """
    if type(component_id) is not int or component_id < 0:
        raise ValueError("invalid Shelly component_id")
    if not isinstance(payload, dict) or "error" in payload:
        raise ValueError("Shelly returned an invalid or failed RPC response")
    if type(payload.get("id")) is not int or payload["id"] != component_id:
        raise ValueError("Shelly component mismatch")
    for key in ("errors", "a_errors", "b_errors", "c_errors", "n_errors"):
        errors = payload.get(key, [])
        if not isinstance(errors, list) or errors:
            raise ValueError("Shelly reports a meter or phase error")
    return _reading(value=payload.get("total_act_power"), unit="W", sign=sign,
                    observed_at=received_at, received_at=received_at, now=now,
                    max_age_seconds=max_age_seconds,
                    source="fixture:shelly_pro3em" if fixture else "shelly_pro3em",
                    timestamp_quality="fixture_receipt" if fixture else "poll_receipt",
                    timestamp_basis="local_receipt_not_device_sample",
                    phase_count=phase_count)


def parse_home_assistant(payload: dict, *, entity_id: str, unit: str,
                         received_at: datetime, now: datetime, sign: str,
                         phase_count: int | None = None, max_age_seconds: int = 120,
                         fixture: bool = False) -> MeterReading:
    """Normalize one explicitly mapped HA grid power sensor (including Sigenergy).

    last_reported means HA received a report, not that hardware was sampled.
    last_updated is only a fallback state-change time. Both remain unverified.
    """
    _entity(entity_id)
    if not isinstance(payload, dict) or payload.get("entity_id") != entity_id:
        raise ValueError("Home Assistant meter entity mismatch")
    attributes = payload.get("attributes")
    if not isinstance(attributes, dict) or attributes.get("unit_of_measurement") != unit:
        raise ValueError("Home Assistant unit differs from configured meter unit")
    field = "last_reported" if payload.get("last_reported") is not None else "last_updated"
    observed = _parse_time(payload.get(field))
    return _reading(value=payload.get("state"), unit=unit, sign=sign,
                    observed_at=observed, received_at=received_at, now=now,
                    max_age_seconds=max_age_seconds,
                    source="fixture:home_assistant" if fixture else "home_assistant",
                    timestamp_quality="unverified", timestamp_basis="home_assistant." + field,
                    phase_count=phase_count, numeric_string=True)


def _origin(value) -> str:
    message = "use an HTTP(S) meter origin without credentials, path, query or fragment"
    if (not isinstance(value, str) or "?" in value or "#" in value or
        any(ord(c) <= 32 or ord(c) == 127 for c in value)):
        raise ValueError(message)
    try:
        parsed = urlparse(value)
        port = parsed.port
        host = parsed.hostname
    except ValueError:
        raise ValueError(message) from None
    if (parsed.scheme not in ("http", "https") or not host or
        parsed.username is not None or parsed.password is not None or
        parsed.query or parsed.fragment or parsed.path not in ("", "/") or
        (port is not None and not 1 <= port <= 65535)):
        raise ValueError(message)
    if ":" in host:
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            raise ValueError(message) from None
    elif not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.?", host):
        raise ValueError(message)
    return value.rstrip("/")


def _entity(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sensor\.[a-z0-9_]+", value):
        raise ValueError("configure a numeric sensor entity_id")
    return value


def _get_json(url: str, *, headers: dict, timeout: float, opener=None) -> dict:
    # Local LAN requests bypass environment proxies; credentials never follow a redirect.
    transport = opener if opener is not None else build_opener(ProxyHandler({}), NoMeterRedirect())
    request = Request(url, headers=headers, method="GET")
    try:
        with transport.open(request, timeout=timeout) as response:
            if hasattr(response, "geturl") and response.geturl() != url:
                raise ValueError("unexpected response URL")
            if hasattr(response, "getcode") and response.getcode() != 200:
                raise ValueError("unexpected HTTP status")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, ValueError) as exc:
        if isinstance(exc, HTTPError):
            exc.close()
        raise ValueError("meter request failed; check address, authentication and connection") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("oversized meter response")
    try:
        def reject_constant(value):
            raise ValueError("non-finite JSON number")
        payload = json.loads(raw, parse_constant=reject_constant)
    except (ValueError, UnicodeError):
        raise ValueError("meter response is not valid finite JSON") from None
    if not isinstance(payload, dict):
        raise ValueError("meter response must be an object")
    return payload


def _config(config: dict) -> None:
    """Reject misspellings and saved credentials instead of silently ignoring them."""
    if not isinstance(config, dict):
        raise ValueError("meter configuration must be an object")
    if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise ValueError("meter schema_version must be 1")
    adapter = config.get("adapter")
    fixture = adapter == "fixture"
    source = config.get("source_adapter") if fixture else adapter
    if source not in ("shelly_pro3em", "home_assistant"):
        raise ValueError("unsupported meter adapter")
    required = {"schema_version", "adapter", "sign"}
    allowed = required | {"phase_count", "max_age_seconds"}
    if fixture:
        required |= {"source_adapter", "received_at", "payload"}
    else:
        required |= {"base_url"}
        allowed |= {"timeout_seconds"}
    if source == "home_assistant":
        required |= {"entity_id", "unit"}
        if not fixture:
            allowed |= {"token_env"}
    else:
        allowed |= {"component_id"}
    allowed |= required
    if set(config) - allowed:
        raise ValueError("unsupported meter configuration field; use environment variables for credentials")
    if required - set(config):
        raise ValueError("missing required meter configuration field")


def read_meter(config: dict, *, now: datetime | None = None, opener=None) -> MeterReading:
    """One read-only poll or fixture normalization; never writes to equipment.

    config requires schema_version: 1, adapter and an explicit sign. Unknown keys
    (including embedded credentials) are rejected. Shelly uses base_url and optional
    component_id. HA uses base_url, entity_id, unit and token_env (default HA_TOKEN).
    Shelly digest authentication is not implemented: use an authenticated HA
    integration for protected devices; do not disable device authentication.
    Fixtures need source_adapter, payload and the original received_at ISO time.
    Omit ``now`` for live reads to record receipt after the HTTP response; passing
    ``now`` freezes the reference clock for deterministic tests/replay.
    A custom opener is a trusted transport/testing hook and must also refuse redirects.
    """
    _config(config)
    fixed_clock = now is not None
    now = now if fixed_clock else _utc_now()
    maximum = config.get("max_age_seconds", 120)
    _policy(now, maximum)
    sign = config.get("sign")
    _power(0, "W", sign)
    phases = _phase_count(config.get("phase_count"))
    adapter = config.get("adapter")
    fixture = adapter == "fixture"
    if fixture:
        adapter = config.get("source_adapter")
        received = _parse_time(config.get("received_at"))
        payload = config.get("payload")
    else:
        received = now
        timeout = config.get("timeout_seconds", 5)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
            raise ValueError("meter timeout_seconds must be from 0 to 30 seconds")
        origin = _origin(config.get("base_url"))
        if adapter == "shelly_pro3em":
            component = config.get("component_id", 0)
            if type(component) is not int or component < 0:
                raise ValueError("invalid Shelly component_id")
            payload = _get_json(origin + "/rpc/EM.GetStatus?id=" + str(component),
                                headers={}, timeout=timeout, opener=opener)
        elif adapter == "home_assistant":
            entity = _entity(config.get("entity_id"))
            token_env = config.get("token_env", "HA_TOKEN")
            if not isinstance(token_env, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token_env):
                raise ValueError("invalid meter token environment variable name")
            token = os.environ.get(token_env, "")
            if not token or any(ord(c) <= 32 or ord(c) == 127 for c in token):
                raise ValueError("meter token environment variable is missing or invalid")
            payload = _get_json(origin + "/api/states/" + quote(entity, safe=""),
                                headers={"Authorization": "Bearer " + token},
                                timeout=timeout, opener=opener)
        else:
            raise ValueError("unsupported meter adapter")
        if not fixed_clock:
            now = received = _utc_now()
    common = dict(received_at=received, now=now, sign=sign, phase_count=phases,
                  max_age_seconds=maximum, fixture=fixture)
    if adapter == "shelly_pro3em":
        return parse_shelly(payload, component_id=config.get("component_id", 0), **common)
    if adapter == "home_assistant":
        return parse_home_assistant(payload, entity_id=config.get("entity_id"),
                                    unit=config.get("unit"), **common)
    raise ValueError("unsupported meter fixture adapter")
