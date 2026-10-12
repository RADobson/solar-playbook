import argparse
from dataclasses import asdict, replace
from http.client import HTTPException
import json
import os
from pathlib import Path
from xml.etree.ElementTree import ParseError

from .advisor import advise
from .cloud_advisor import AIConfig, AllowanceLedger, advise_cloud
from .demo import scenario
from .forecast import parse_bom_xml
from .home_assistant import HomeAssistant
from .model import Scenario, timestamp
from .metering import read_meter
from .vehicles import resolve_vehicle_request
from .charging import ChargerConfig, Evcc, MODES, handoff_mode
from .planner import plan
from .report import render


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Local energy planning and read-only adapters; explicit attended evcc handoff")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run a synthetic day")
    demo.add_argument("--scenario", choices=("sunny", "cloudy", "away", "impossible", "stale"), default="sunny")
    demo.add_argument("--out", type=Path, default=Path("out/sunny"))
    demo_ai = demo.add_mutually_exclusive_group()
    demo_ai.add_argument("--ollama", action="store_true", help="Optional local explanation")
    demo_ai.add_argument("--ai-config", type=Path, help="Explicit cloud provider configuration")
    demo.add_argument("--ai-ledger", type=Path, default=Path("private/ai-allowance.sqlite3"))
    run = commands.add_parser("plan", help="Plan a provider-neutral scenario JSON")
    run.add_argument("input", type=Path)
    run.add_argument("--out", type=Path, default=Path("out/plan"))
    run_ai = run.add_mutually_exclusive_group()
    run_ai.add_argument("--ollama", action="store_true")
    run_ai.add_argument("--ai-config", type=Path)
    run.add_argument("--ai-ledger", type=Path, default=Path("private/ai-allowance.sqlite3"))
    for command in (demo, run):
        command.add_argument("--vehicle-request", type=Path, help="Brand-neutral energy or SOC request JSON")
        command.add_argument("--vehicle-state", type=Path, help="Recorded HA SOC fixture (requires --vehicle-request)")
        command.add_argument("--at", help="Aware reference time for fixture replay only")
    bom = commands.add_parser("bom", help="Parse a locally downloaded BoM XML product")
    bom.add_argument("input", type=Path)
    bom.add_argument("--area", required=True, help="Exact BoM area AAC from the product")
    ha = commands.add_parser("ha-read", help="Read one HA entity; never call a service")
    ha.add_argument("entity")
    ha.add_argument("--url", default="http://homeassistant.local:8123")
    meter = commands.add_parser("meter-read", help="Normalize a read-only grid-power observation")
    meter.add_argument("config", type=Path)
    meter.add_argument("--at", help="Aware reference time; fixture configs only")
    evcc = commands.add_parser("evcc-read", help="Read a configured evcc loadpoint")
    evcc.add_argument("config", type=Path)
    mode = commands.add_parser("charge-mode", help="Preview one evcc mode handoff; modes persist")
    mode.add_argument("config", type=Path)
    mode.add_argument("mode", choices=MODES)
    mode.add_argument("--expected-mode", choices=MODES, required=True)
    mode.add_argument("--apply", action="store_true", help="Send a real persistent mode change to evcc")
    mode.add_argument("--attended", action="store_true", help="Confirm an attended commissioning session")
    mode.add_argument("--out", type=Path, help="Save a private handoff receipt")
    devices = commands.add_parser("device-demo", help="Run the complete synthetic multi-brand example offline")
    devices.add_argument("--out", type=Path, default=Path("out/devices"))
    args = parser.parse_args(argv)
    try:
        if args.command == "device-demo":
            from .integration_demo import run_demo
            print(json.dumps(run_demo(args.out), indent=2))
            return 0
        if args.command == "meter-read":
            config = json.loads(args.config.read_text())
            if args.at and config.get("adapter") != "fixture":
                raise ValueError("reference time is only permitted for fixtures")
            reading = read_meter(config, now=timestamp(args.at) if args.at else None)
            print(json.dumps(reading.as_dict(), indent=2))
            return 0
        if args.command in ("evcc-read", "charge-mode"):
            config = ChargerConfig.from_dict(json.loads(args.config.read_text()))
            if args.command == "evcc-read":
                result = Evcc(config).read().as_dict()
                status = 0
            else:
                result = handoff_mode(config, args.mode, expected_mode=args.expected_mode,
                                      apply=args.apply, attended=args.attended)
                status = 0 if result["eligible"] and result["status"] != "unconfirmed" else 2
                if args.out:
                    try:
                        args.out.parent.mkdir(parents=True, exist_ok=True)
                        args.out.write_text(json.dumps(result, indent=2) + "\n")
                    except OSError:
                        # Preserve a potentially successful/unknown POST outcome in stdout.
                        result["receipt_storage_error"] = "Could not save receipt; retain this output and inspect evcc before retrying."
                        status = 2
            print(json.dumps(result, indent=2))
            return status
        if args.command == "bom":
            print(json.dumps(parse_bom_xml(args.input.read_text(), args.area), indent=2))
            return 0
        if args.command == "ha-read":
            token = os.environ.get("HA_TOKEN", "")
            print(json.dumps(HomeAssistant(args.url, token).state(args.entity), indent=2))
            return 0
        data = scenario(args.scenario) if args.command == "demo" else Scenario.from_dict(json.loads(args.input.read_text()))
        vehicle = None
        if args.vehicle_state and not args.vehicle_request:
            raise ValueError("vehicle state requires a vehicle request")
        if args.at and not args.vehicle_state:
            raise ValueError("reference time requires a recorded vehicle state")
        if args.vehicle_request:
            vehicle = resolve_vehicle_request(json.loads(args.vehicle_request.read_text()),
                now=timestamp(args.at) if args.at else None,
                state=json.loads(args.vehicle_state.read_text()) if args.vehicle_state else None)
            data = replace(data, ev_required_kwh=vehicle.required_battery_kwh,
                           site=replace(data.site, ev_efficiency=vehicle.charging_efficiency))
        report = plan(data)
        if vehicle:
            report["vehicle_request"] = asdict(vehicle)
        if args.ollama:
            report["advice"] = advise(report)
        elif args.ai_config:
            config = AIConfig(**json.loads(args.ai_config.read_text()))
            report["advice"] = advise_cloud(report, config, AllowanceLedger(args.ai_ledger))
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "input.json").write_text(json.dumps(asdict(data), indent=2) + "\n")
        (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "report.html").write_text(render(report))
        selected = report.get("selected")
        print(json.dumps({"status": report["status"], "output": str(args.out),
                          "strategy": selected["strategy"] if selected else None,
                          "hardware_writes": 0}, indent=2))
        return 0 if selected else 2
    except (ValueError, KeyError, TypeError, OSError, HTTPException, OverflowError, ParseError) as exc:
        # Do not echo tokens or HTTP response bodies.
        parser.exit(1, f"Input or connection error: {type(exc).__name__}. Check config and freshness.\n")


if __name__ == "__main__":
    raise SystemExit(main())
