"""A fully offline example of the adapter -> request -> planner -> preview path."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path

from .charging import ChargerConfig, handoff_mode, parse_state
from .demo import scenario
from .metering import read_meter
from .planner import plan
from .report import render
from .vehicles import resolve_vehicle_request


def run_demo(out: Path) -> dict:
    now = datetime(2030, 1, 15, 0, 0, tzinfo=timezone.utc)
    meter_config = {"schema_version": 1, "adapter": "fixture", "source_adapter": "shelly_pro3em",
                    "received_at": now.isoformat(), "sign": "import_positive", "phase_count": 1,
                    "payload": {"id": 0, "total_act_power": -2500}}
    request = {"schema_version": 1, "mode": "add_energy", "energy_kwh": 15,
               "energy_basis": "wall", "charging_efficiency": 0.9}
    meter = read_meter(meter_config, now=now)
    target = resolve_vehicle_request(request, now=now)
    original = scenario()
    data = replace(original, ev_required_kwh=target.required_battery_kwh,
                   site=replace(original.site, ev_efficiency=target.charging_efficiency))
    report = plan(data)
    report["vehicle_request"] = asdict(target)
    config = ChargerConfig(base_url="http://127.0.0.1:7070", loadpoint_id=1,
                           expected_loadpoint_name="synthetic-garage", control_enabled=True,
                           commissioning_id="SYNTHETIC-NOT-A-REAL-INSTALLATION",
                           independent_limits_verified=True, fallback_verified=True)
    state = {"version": "0.317.1", "apiReady": True, "startupCompleted": True,
             "setupRequired": False, "loadpoints": [{"name": "synthetic-garage", "vehicleName": "",
             "mode": "off", "connected": True, "chargePower": 0, "maxCurrent": 16, "phasesConfigured": 1}]}

    class FixtureController:
        def __init__(self):
            self.config = config
        def clock(self):
            return now
        def read(self):
            return replace(parse_state(state, config, received_at=now),
                           source="fixture:evcc", timestamp_quality="synthetic_fixture")
        def _set_mode(self, mode):
            raise AssertionError("a demo must never issue a controller write")

    handoff = handoff_mode(config, "smart", expected_mode="off", client=FixtureController())
    result = {"schema_version": 1, "execution": "synthetic_offline_demo", "network_requests": 0,
              "controller_writes": 0, "meter": meter.as_dict(), "vehicle_request": asdict(target),
              "handoff": handoff,
              "boundary": "Live grid power is demonstrated as an observation, not substituted for a day-ahead forecast. The mode preview is separate from the simulated amp schedule."}
    out.mkdir(parents=True, exist_ok=True)
    for name, value in (("input.json", asdict(data)), ("report.json", report), ("devices.json", result),
                        ("meter-fixture.json", meter_config), ("vehicle-request.json", request)):
        (out / name).write_text(json.dumps(value, indent=2) + "\n")
    (out / "report.html").write_text(render(report))
    return {"status": report["status"], "output": str(out), "network_requests": 0,
            "controller_writes": 0, "vehicle_api_required": False,
            "requested_wall_kwh": 15, "required_battery_kwh": target.required_battery_kwh}
