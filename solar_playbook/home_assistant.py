"""Read-only HA adapter. This adapter never calls equipment-write endpoints."""
from datetime import datetime
import json
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

from .model import finite, timestamp


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("HA redirect refused; configure its final URL directly")


class HomeAssistant:
    def __init__(self, base_url: str, token: str):
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("use an HTTP(S) HA URL without credentials")
        if parsed.query or parsed.fragment or parsed.path.rstrip("/"):
            raise ValueError("use the HA origin, e.g. http://homeassistant.local:8123")
        if not token or "\n" in token or "\r" in token:
            raise ValueError("invalid HA token")
        self.base_url = base_url.rstrip("/")
        self.token = token

    def state(self, entity_id: str) -> dict:
        if not entity_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_." for c in entity_id):
            raise ValueError("invalid entity id")
        request = Request(self.base_url + "/api/states/" + quote(entity_id, safe=""),
                          headers={"Authorization": "Bearer " + self.token})
        with build_opener(NoRedirect).open(request, timeout=5) as response:
            raw = response.read(100_001)
        if len(raw) > 100_000:
            raise ValueError("oversized HA state")
        state = json.loads(raw)
        if state.get("entity_id") != entity_id:
            raise ValueError("HA entity mismatch")
        return state


def numeric_state(state: dict, *, unit: str, now: datetime, max_age_seconds: int = 120) -> float:
    if now.utcoffset() is None or not 1 <= max_age_seconds <= 3600:
        raise ValueError("invalid freshness policy")
    value = float(state["state"])
    finite(value, "HA value")
    if state.get("attributes", {}).get("unit_of_measurement") != unit:
        raise ValueError("unexpected HA unit; convert explicitly at the adapter")
    reported = state.get("last_reported") or state.get("last_updated")
    if not reported:
        raise ValueError("missing HA freshness timestamp")
    age = (now - timestamp(reported)).total_seconds()
    if not 0 <= age <= max_age_seconds:
        raise ValueError("stale or future HA state")
    return value


def proposal_gate(*, now: datetime, valid_from: str, valid_until: str,
                  observed_at: str, manual_override: bool, home: bool,
                  plugged_in: bool, commissioned: bool, requested_amps: int,
                  max_amps: int = 32) -> dict:
    """Pure decision contract for a future actuator; never sends a command.

    observed_at must be an equipment heartbeat, not the scheduler's own clock.
    A future actuator must recheck immediately before applying a command.
    """
    for flag in (manual_override, home, plugged_in, commissioned):
        if type(flag) is not bool:
            raise ValueError("gate flags must be booleans; unknown is not false")
    if now.utcoffset() is None:
        raise ValueError("gate requires aware time")
    start, end, observed = map(timestamp, (valid_from, valid_until, observed_at))
    reasons = []
    if not start <= now < end or (end - start).total_seconds() > 90:
        reasons.append("expired, future or excessive command lease")
    if not 0 <= (now - observed).total_seconds() <= 90:
        reasons.append("equipment telemetry is stale or in the future")
    if manual_override:
        reasons.append("manual override owns control")
    if not home or not plugged_in:
        reasons.append("vehicle is not confirmed home and plugged in")
    if not commissioned:
        reasons.append("site is not commissioned for external control")
    if (type(max_amps) is not int or not 6 <= max_amps <= 80 or
        type(requested_amps) is not int or
        (requested_amps != 0 and not 6 <= requested_amps <= max_amps)):
        reasons.append("current is outside commissioned limits")
    return {"eligible": not reasons, "reasons": reasons, "requested_amps": requested_amps,
            "hardware_write_performed": False}
