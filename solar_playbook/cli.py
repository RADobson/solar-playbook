import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from xml.etree.ElementTree import ParseError

from .advisor import advise
from .cloud_advisor import AIConfig, AllowanceLedger, advise_cloud
from .demo import scenario
from .forecast import parse_bom_xml
from .home_assistant import HomeAssistant
from .model import Scenario
from .planner import plan
from .report import render


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Local energy planning; no hardware writes")
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
    bom = commands.add_parser("bom", help="Parse a locally downloaded BoM XML product")
    bom.add_argument("input", type=Path)
    bom.add_argument("--area", required=True, help="Exact BoM area AAC from the product")
    ha = commands.add_parser("ha-read", help="Read one HA entity; never call a service")
    ha.add_argument("entity")
    ha.add_argument("--url", default="http://homeassistant.local:8123")
    args = parser.parse_args(argv)
    try:
        if args.command == "bom":
            print(json.dumps(parse_bom_xml(args.input.read_text(), args.area), indent=2))
            return 0
        if args.command == "ha-read":
            token = os.environ.get("HA_TOKEN", "")
            print(json.dumps(HomeAssistant(args.url, token).state(args.entity), indent=2))
            return 0
        data = scenario(args.scenario) if args.command == "demo" else Scenario.from_dict(json.loads(args.input.read_text()))
        report = plan(data)
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
    except (ValueError, KeyError, TypeError, OSError, ParseError) as exc:
        # Do not echo tokens or HTTP response bodies.
        parser.exit(1, f"Input or connection error: {type(exc).__name__}. Check config and freshness.\n")


if __name__ == "__main__":
    raise SystemExit(main())
