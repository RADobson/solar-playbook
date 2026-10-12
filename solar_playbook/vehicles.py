"""Brand-neutral, read-only translation of charging requests into battery kWh.

An EVSE can deliver energy without a vehicle API. A percentage target additionally
needs a commissioned SOC mapping and an explicit capacity estimate. This module
does not identify vehicles, wake them, or issue charger/car commands.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re

from .home_assistant import HomeAssistant
from .model import finite, timestamp


@dataclass(frozen=True)
class VehicleRequestResult:
    mode: str
    required_battery_kwh: float
    charging_efficiency: float
    target_description: str
    quality: str
    provenance: dict
    assumptions: tuple[str, ...]


def _keys(value: dict, *, required: set[str], optional: set[str], label: str) -> None:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object with string keys")
    if set(value) - required - optional:
        raise ValueError(f"unknown {label} keys")
    if required - set(value):
        raise ValueError(f"missing required {label} keys")


def _number(value, label: str, low: float, high: float, *, exclusive_low: bool = False) -> float:
    try:
        finite(value, label)
    except OverflowError:
        raise ValueError(f"{label} must be a finite supported number") from None
    if not low <= value <= high or (exclusive_low and value == low):
        raise ValueError(f"{label} is outside the supported range")
    return float(value)


def _telemetry_config(config: dict) -> None:
    _keys(config, required={"source", "entity_id", "timestamp_field", "max_age_seconds"},
          optional={"base_url", "token_env"}, label="telemetry")
    if config["source"] != "home_assistant":
        raise ValueError("only mapped Home Assistant vehicle telemetry is implemented")
    entity = config["entity_id"]
    if not isinstance(entity, str) or not re.fullmatch(r"sensor\.[a-z0-9_]+", entity):
        raise ValueError("SOC entity_id must identify a Home Assistant sensor")
    field = config["timestamp_field"]
    if (not isinstance(field, str) or
        (field not in ("last_updated", "last_reported") and
         not re.fullmatch(r"attributes\.[A-Za-z0-9_]+", field))):
        raise ValueError("timestamp_field must be last_updated, last_reported or attributes.<name>")
    age = config["max_age_seconds"]
    if type(age) is not int or not 1 <= age <= 3600:
        raise ValueError("SOC max_age_seconds must be an integer in [1, 3600]")
    if ("base_url" in config) != ("token_env" in config):
        raise ValueError("configure both HA base_url and token_env, or inject a client/state")
    if "base_url" in config:
        if not isinstance(config["base_url"], str):
            raise ValueError("HA base_url must be a string")
        # Reuse origin validation without performing any request.
        HomeAssistant(config["base_url"], "validation-only")
        name = config["token_env"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("token_env must be an environment variable name, not a token")


def _read_soc(config: dict, *, now: datetime | None, state: dict | None,
              client: HomeAssistant | None) -> tuple[float, dict, tuple[str, ...]]:
    _telemetry_config(config)
    if state is not None and client is not None:
        raise ValueError("supply a state or an HA client, not both")
    read_method = "injected_state" if state is not None else "home_assistant_get"
    if state is None:
        if client is None:
            if "base_url" not in config:
                raise ValueError("SOC requires a state, an HA client, or configured HA connection")
            token = os.environ.get(config["token_env"], "")
            if not token:
                raise ValueError("HA token environment variable is missing")
            client = HomeAssistant(config["base_url"], token)
        try:
            state = client.state(config["entity_id"])
        except (OSError, ValueError, TypeError, KeyError):
            # Avoid reflecting provider responses or credentials into CLI output.
            raise ValueError("vehicle telemetry unavailable; no SOC target was inferred") from None
    if not isinstance(state, dict) or state.get("entity_id") != config["entity_id"]:
        raise ValueError("vehicle telemetry entity mismatch")
    attributes = state.get("attributes")
    if not isinstance(attributes, dict) or attributes.get("unit_of_measurement") != "%":
        raise ValueError("SOC requires an explicit % unit; fractions are not converted implicitly")
    raw = state.get("state")
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        raise ValueError("SOC must be a finite percentage, not an unknown value")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("SOC unavailable; no SOC target was inferred") from None
    value = _number(value, "SOC", 0, 100)
    field = config["timestamp_field"]
    source_timestamp = (attributes.get(field.split(".", 1)[1])
                        if field.startswith("attributes.") else state.get(field))
    try:
        observed = timestamp(source_timestamp)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("vehicle telemetry is missing a valid aware source timestamp") from None
    # Capture the live clock after a blocking read: a legitimate upstream update
    # during that read must not look newer than a pre-request reference time.
    reference_time = now if now is not None else datetime.now(timezone.utc)
    age = (reference_time - observed).total_seconds()
    if not 0 <= age <= config["max_age_seconds"]:
        raise ValueError("vehicle SOC is stale or in the future; no SOC target was inferred")
    source_time = field.startswith("attributes.")
    assumptions = (() if source_time else (
        "The timestamp measures Home Assistant state freshness; it does not prove the vehicle's upstream reading is fresh.",
    ))
    return value, {
        "source": "home_assistant", "entity_id": config["entity_id"],
        "read_method": read_method, "soc_percent": value,
        "observed_at": observed.isoformat(), "age_seconds": age,
        "timestamp_field": field,
        "timestamp_basis": "mapped_source_observation" if source_time else "home_assistant_state",
        "max_age_seconds": config["max_age_seconds"],
    }, assumptions


def resolve_vehicle_request(config: dict, *, now: datetime | None = None, state: dict | None = None,
                            client: HomeAssistant | None = None) -> VehicleRequestResult:
    """Resolve one request; failures never silently become a zero-SOC reading.

    ``add_energy`` uses an explicit ``wall`` or ``battery`` energy basis and
    works entirely offline. ``target_soc`` reads an injected HA state, an
    injected HomeAssistant client, or a configured origin plus token environment
    variable. A mapped source timestamp is preferred to HA's own update time.
    Omit now for live reads; freshness is evaluated after acquiring the state.
    Pass an aware now to preserve a fixed reference time for replay or tests.

    Set Scenario.ev_required_kwh to required_battery_kwh AND use the returned
    charging_efficiency as Site.ev_efficiency to preserve wall/battery units.
    The existing scenario still supplies availability and departure deadline.
    """
    if now is not None and (not isinstance(now, datetime) or now.utcoffset() is None):
        raise ValueError("vehicle request resolution requires timezone-aware now")
    if not isinstance(config, dict):
        raise ValueError("vehicle request must be an object")
    common = {"schema_version", "mode", "charging_efficiency"}
    mode = config.get("mode")
    if mode == "add_energy":
        required = common | {"energy_kwh", "energy_basis"}
    elif mode == "target_soc":
        required = common | {"target_soc_percent", "capacity_kwh", "capacity_basis", "telemetry"}
    else:
        raise ValueError("vehicle mode must be add_energy or target_soc")
    _keys(config, required=required, optional=set(), label="vehicle request")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("unsupported vehicle request schema_version")
    efficiency = _number(config["charging_efficiency"], "charging_efficiency", 0, 1,
                         exclusive_low=True)
    if mode == "add_energy":
        if state is not None or client is not None:
            raise ValueError("add_energy does not use vehicle telemetry")
        amount = _number(config["energy_kwh"], "energy_kwh", 0, 200)
        basis = config["energy_basis"]
        if basis not in ("wall", "battery"):
            raise ValueError("energy_basis must be wall or battery")
        result = amount * efficiency if basis == "wall" else amount
        return VehicleRequestResult(
            mode=mode, required_battery_kwh=result, charging_efficiency=efficiency,
            target_description=f"Add {amount:g} kWh measured at the {basis}",
            quality="estimated_conversion" if basis == "wall" else "user_energy_request",
            provenance={"source": "user_request", "energy_kwh": amount, "energy_basis": basis},
            assumptions=("Charging efficiency is a configured estimate; delivered energy and final SOC are not measured here.",
                         "The vehicle's own charge limit or charge acceptance can prevent the requested delivery."),
        )
    target = _number(config["target_soc_percent"], "target_soc_percent", 0, 100)
    capacity = _number(config["capacity_kwh"], "capacity_kwh", 0, 200, exclusive_low=True)
    basis = config["capacity_basis"]
    if basis not in ("usable", "nominal"):
        raise ValueError("capacity_basis must explicitly be usable or nominal")
    current, provenance, warnings = _read_soc(config["telemetry"], now=now, state=state, client=client)
    result = _number(max(0.0, target - current) / 100 * capacity,
                     "required_battery_kwh", 0, 200)
    assumptions = (
        "SOC-to-energy conversion is an estimate; degradation, buffers, temperature and rounding affect it.",
        "The configured capacity must refer to this vehicle; manufacturer nominal capacity can overstate usable capacity.",
        "This is a planning target, not a command to change the vehicle's own charge limit.",
    ) + warnings
    return VehicleRequestResult(
        mode=mode, required_battery_kwh=result, charging_efficiency=efficiency,
        target_description=f"Reach {target:g}% from reported {current:g}% SOC",
        quality="estimated_soc_energy" if provenance["timestamp_basis"] == "mapped_source_observation"
                else "estimated_soc_energy_ha_timestamp_only",
        provenance=provenance | {"target_soc_percent": target, "capacity_kwh": capacity,
                                 "capacity_basis": basis}, assumptions=assumptions,
    )
