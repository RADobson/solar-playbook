"""Read evcc state and hand off one attended mode change.

The evcc driver owns charger commands. This is not a control loop, OCPP server,
physical interlock, or expiring hardware lease. It never changes current limits.
Contract reference: evcc 0.317.1 server/openapi{,.state}.yaml.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.client import HTTPException
import json
import os
import re
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .model import finite

MODES = ("off", "smart", "now")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("evcc redirects are not followed")


@dataclass(frozen=True)
class ChargerConfig:
    base_url: str
    loadpoint_id: int
    expected_loadpoint_name: str
    expected_version: str = "0.317.1"
    token_env: str | None = None
    expected_vehicle_name: str | None = None
    control_enabled: bool = False
    commissioning_id: str = ""
    independent_limits_verified: bool = False
    fallback_verified: bool = False
    max_current_amps: float = 16
    phases: int = 1
    allowed_modes: tuple[str, ...] = ("off", "smart")
    max_request_seconds: int = 15

    @classmethod
    def from_dict(cls, raw: dict) -> "ChargerConfig":
        if not isinstance(raw, dict):
            raise ValueError("expected an evcc config object")
        raw = dict(raw)
        version = raw.pop("schema_version", None)
        if type(version) is not int or version != 1 or raw.get("adapter") != "evcc":
            raise ValueError("expected an evcc config")
        # Check the exact schema version separately (bool is not a version).
        if raw.pop("adapter") != "evcc":
            raise ValueError("unsupported charger adapter")
        if "allowed_modes" in raw:
            if not isinstance(raw["allowed_modes"], list):
                raise ValueError("allowed_modes must be a list")
            raw["allowed_modes"] = tuple(raw["allowed_modes"])
        result = cls(**raw)
        result.validate()
        return result

    def validate(self):
        if not isinstance(self.base_url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in self.base_url):
            raise ValueError("invalid evcc origin")
        p = urlparse(self.base_url)
        if (p.scheme not in ("http", "https") or not p.hostname or p.username or p.password
                or p.query or p.fragment or p.path.rstrip("/")):
            raise ValueError("use an evcc origin without credentials or path")
        if p.port is not None and not 1 <= p.port <= 65535:
            raise ValueError("invalid evcc port")
        if type(self.loadpoint_id) is not int or not 1 <= self.loadpoint_id <= 100:
            raise ValueError("invalid 1-based loadpoint index")
        for value in (self.expected_loadpoint_name, self.expected_version):
            if not isinstance(value, str) or not 1 <= len(value) <= 100 or any(ord(c) < 32 for c in value):
                raise ValueError("missing expected controller identity")
        if self.expected_vehicle_name is not None and not isinstance(self.expected_vehicle_name, str):
            raise ValueError("invalid expected vehicle name")
        if self.token_env is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.token_env):
            raise ValueError("invalid token environment variable")
        if any(type(v) is not bool for v in (self.control_enabled, self.independent_limits_verified, self.fallback_verified)):
            raise ValueError("commissioning flags must be booleans")
        if not isinstance(self.commissioning_id, str) or len(self.commissioning_id) > 120:
            raise ValueError("invalid commissioning reference")
        finite(self.max_current_amps, "max current")
        if not 6 <= self.max_current_amps <= 80 or type(self.phases) is not int or self.phases not in (1, 3):
            raise ValueError("invalid commissioned current/phases")
        if not self.allowed_modes or any(m not in MODES for m in self.allowed_modes):
            raise ValueError("invalid allowed modes")
        if type(self.max_request_seconds) is not int or not 1 <= self.max_request_seconds <= 30:
            raise ValueError("invalid request window")


@dataclass(frozen=True)
class ChargerReading:
    source: str
    received_at: str
    timestamp_quality: str
    version: str | None
    loadpoint_id: int
    loadpoint_name: str
    vehicle_name: str | None
    mode: str
    connected: bool
    charge_power_kw: float
    max_current_amps: float
    phases: int
    api_ready: bool
    startup_completed: bool
    setup_required: bool
    disabled: bool

    def as_dict(self):
        return asdict(self)


def parse_state(state: dict, config: ChargerConfig, *, received_at: datetime) -> ChargerReading:
    config.validate()
    if received_at.utcoffset() is None or not isinstance(state, dict):
        raise ValueError("invalid controller observation")
    points = state.get("loadpoints")
    if not isinstance(points, list) or len(points) < config.loadpoint_id:
        raise ValueError("loadpoint not found")
    point = points[config.loadpoint_id - 1]
    if not isinstance(point, dict) or point.get("name") != config.expected_loadpoint_name:
        raise ValueError("loadpoint identity mismatch; indices may have changed")
    if point.get("mode") not in MODES or type(point.get("connected")) is not bool:
        raise ValueError("unsupported mode or unknown connection state")
    for key in ("chargePower", "maxCurrent"):
        finite(point.get(key), key)
        if point[key] < 0:
            raise ValueError("negative charging power/current")
    phases = point.get("phasesConfigured")
    if type(phases) is not int or phases not in (0, 1, 3):
        raise ValueError("unknown phase configuration")
    # Zero means automatic phase switching: readable, not qualified by this adapter.
    version = state.get("version")
    if version is not None and not isinstance(version, str):
        raise ValueError("invalid controller version")
    vehicle = point.get("vehicleName")
    if vehicle is not None and not isinstance(vehicle, str):
        raise ValueError("invalid vehicle identity")
    for mapping, keys in ((state, ("apiReady", "startupCompleted", "setupRequired")), (point, ("disabled",))):
        for key in keys:
            if key in mapping and type(mapping[key]) is not bool:
                raise ValueError("unknown controller readiness")
    return ChargerReading("evcc", received_at.isoformat(), "controller_poll_receipt",
                          version, config.loadpoint_id, point["name"], vehicle,
                          point["mode"], point["connected"], point["chargePower"] / 1000,
                          point["maxCurrent"], phases, state.get("apiReady", False),
                          state.get("startupCompleted", False), state.get("setupRequired", True),
                          point.get("disabled", False))


class Evcc:
    def __init__(self, config: ChargerConfig, *, opener=None, clock=None):
        config.validate()
        self.config = config
        self.opener = opener or build_opener(ProxyHandler({}), NoRedirect)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.token = os.environ.get(config.token_env, "") if config.token_env else None
        if config.token_env and (not self.token or any(ord(c) < 32 for c in self.token)):
            raise ValueError("configured evcc token is missing or invalid")

    def _request(self, path: str, method: str = "GET"):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = Request(self.config.base_url.rstrip("/") + "/api" + path,
                      headers=headers, method=method, data=b"" if method == "POST" else None)
        try:
            with self.opener.open(req, timeout=5) as response:
                data = response.read(1_000_001)
        except HTTPError as exc:
            exc.close()
            raise ValueError("evcc HTTP request failed") from None
        if len(data) > 1_000_000:
            raise ValueError("oversized controller response")
        value = json.loads(data) if data else None
        if isinstance(value, dict) and ("error" in value or "errors" in value):
            raise ValueError("controller reported an error")
        return value

    def read(self) -> ChargerReading:
        state = self._request("/state")
        return parse_state(state, self.config, received_at=self.clock())

    def _set_mode(self, mode: str):
        # Deliberately private: callers should use handoff_mode for all writes.
        if mode not in MODES:
            raise ValueError("invalid charge mode")
        return self._request(f"/loadpoints/{self.config.loadpoint_id}/mode/{mode}", "POST")


def handoff_mode(config: ChargerConfig, mode: str, *, expected_mode: str,
                 apply: bool = False, attended: bool = False, client: Evcc | None = None) -> dict:
    """Preview or perform one explicit mode handoff; never automatically retry.

    Fresh GET proves contact with evcc, not a fresh meter/device sample. Independent
    electrical protection and commissioned evcc fault handling remain essential.
    expected_mode is a best-effort override check, not an atomic compare-and-swap.
    """
    config.validate()
    if mode not in MODES or expected_mode not in MODES or type(apply) is not bool or type(attended) is not bool:
        raise ValueError("invalid handoff request")
    client = client or Evcc(config)
    if client.config != config:
        raise ValueError("client and handoff configurations differ")
    started = client.clock()
    reading = client.read()
    reasons = []
    if not config.control_enabled or not config.commissioning_id.strip():
        reasons.append("external handoff is not enabled and commissioned")
    if not config.independent_limits_verified or not config.fallback_verified:
        reasons.append("independent limits and native fallback require commissioning")
    if reading.version != config.expected_version:
        reasons.append("evcc version has not been qualified against this configuration")
    if not reading.api_ready or not reading.startup_completed or reading.setup_required or reading.disabled:
        reasons.append("controller is not ready")
    if not reading.connected:
        reasons.append("no vehicle confirmed connected")
    if reading.mode != expected_mode:
        reasons.append("mode changed or an owner override is active")
    if config.expected_vehicle_name is not None and reading.vehicle_name != config.expected_vehicle_name:
        reasons.append("vehicle assignment changed")
    if reading.max_current_amps > config.max_current_amps or reading.phases != config.phases:
        reasons.append("controller limits/phase configuration differ from commissioned limits")
    if mode not in config.allowed_modes:
        reasons.append("requested mode is outside the allowlist")
    elapsed = (client.clock() - started).total_seconds()
    if not 0 <= elapsed <= config.max_request_seconds:
        reasons.append("preflight request window expired")
    receipt = {"schema_version": 1, "status": "preview", "requested_mode": mode,
               "expected_mode": expected_mode, "observation": reading.as_dict(),
               "eligible": not reasons, "reasons": reasons, "controller_write_attempted": False,
               "controller_mode_verified": False, "physical_charging_verified": False,
               "mode_persists": True,
               "note": "Mode persists in evcc. No watchdog or automatic restoration is supplied."}
    if not apply:
        return receipt
    if not attended:
        reasons.append("apply requires an attended commissioning session")
    if reasons:
        receipt.update(status="blocked", eligible=False)
        return receipt
    if reading.mode == mode:
        receipt.update(status="already_selected", controller_mode_verified=True)
        return receipt
    # Once POST is attempted, even a transport error can mean the mode changed.
    receipt["controller_write_attempted"] = True
    try:
        client._set_mode(mode)
        after = client.read()
        receipt["after"] = after.as_dict()
        if after.mode != mode or after.vehicle_name != reading.vehicle_name:
            receipt.update(status="unconfirmed", eligible=False)
            receipt["reasons"].append("read-back differs; inspect evcc before any further action")
        else:
            receipt.update(status="applied", controller_mode_verified=True)
    except (OSError, HTTPException, ValueError, TypeError, KeyError, OverflowError):
        receipt.update(status="unconfirmed", eligible=False)
        receipt["reasons"].append("write outcome is unknown; inspect evcc, do not blindly retry")
    return receipt
