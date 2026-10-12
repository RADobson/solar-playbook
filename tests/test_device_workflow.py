from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from solar_playbook.cli import main

ROOT = Path(__file__).resolve().parents[1]


class DeviceWorkflowTests(unittest.TestCase):
    def run_cli(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_complete_offline_demo_and_meter_replay(self):
        with tempfile.TemporaryDirectory() as folder, patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("offline demo contacted network")):
            code, result = self.run_cli(["device-demo", "--out", folder])
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["network_requests"], 0)
            self.assertEqual(result["controller_writes"], 0)
            path = Path(folder)
            devices = json.loads((path / "devices.json").read_text())
            self.assertEqual(devices["meter"]["grid_power_kw"], -2.5)
            self.assertEqual(devices["handoff"]["status"], "preview")
            self.assertFalse(devices["handoff"]["controller_write_attempted"])
            self.assertEqual(devices["vehicle_request"]["required_battery_kwh"], 13.5)
            self.assertTrue((path / "report.html").is_file())
            code, reading = self.run_cli(["meter-read", str(path / "meter-fixture.json"), "--at", "2030-01-15T00:00:00Z"])
            self.assertEqual(reading["grid_power_kw"], -2.5)
            self.assertFalse(reading["control_eligible"])

    def test_offline_vehicle_request_changes_real_planner_target_and_efficiency(self):
        with tempfile.TemporaryDirectory() as folder:
            code, _ = self.run_cli(["demo", "--vehicle-request", str(ROOT / "examples/vehicle-offline.json"), "--out", folder])
            self.assertEqual(code, 0)
            report = json.loads((Path(folder) / "report.json").read_text())
            self.assertEqual(report["input"]["ev_required_kwh"], 13.5)
            self.assertEqual(report["input"]["site"]["ev_efficiency"], 0.9)
            self.assertGreaterEqual(report["selected"]["ev_added_kwh"], 13.5)
            self.assertIn("vehicle_request", report)

    def test_fresh_soc_fixture_converts_into_plan_and_stale_fixture_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            conf = json.loads((ROOT / "examples/vehicle-byd-ha.json").read_text())
            entity = conf["telemetry"]["entity_id"]
            field = conf["telemetry"]["timestamp_field"].split(".")[1]
            observed = {"entity_id": entity, "state": "50", "attributes": {"unit_of_measurement": "%", field: "2030-01-15T00:00:00Z"}}
            (path / "state.json").write_text(json.dumps(observed))
            args = ["demo", "--vehicle-request", str(ROOT / "examples/vehicle-byd-ha.json"),
                    "--vehicle-state", str(path / "state.json"), "--at", "2030-01-15T00:00:01Z", "--out", str(path / "plan")]
            code, _ = self.run_cli(args)
            self.assertEqual(code, 0)
            report = json.loads((path / "plan/report.json").read_text())
            self.assertAlmostEqual(report["input"]["ev_required_kwh"], (conf["target_soc_percent"] - 50) * conf["capacity_kwh"] / 100)
            args[args.index("--at") + 1] = "2030-01-16T00:00:00Z"
            with self.assertRaises(SystemExit) as failure, redirect_stdout(io.StringIO()), patch("sys.stderr", new_callable=io.StringIO):
                main(args)
            self.assertEqual(failure.exception.code, 1)

    def test_live_meter_cannot_use_a_faked_clock(self):
        with self.assertRaises(SystemExit), patch("sys.stderr", new_callable=io.StringIO), patch("solar_playbook.cli.read_meter") as reader:
            main(["meter-read", str(ROOT / "examples/meter-home-assistant.json"), "--at", "2030-01-15T00:00:00Z"])
        reader.assert_not_called()

    def test_handoff_receipt_failure_preserves_actual_outcome(self):
        receipt = {"status": "applied", "eligible": True, "controller_write_attempted": True,
                   "controller_mode_verified": True, "physical_charging_verified": False}
        with tempfile.TemporaryDirectory() as folder, patch("solar_playbook.cli.handoff_mode", return_value=receipt):
            # Writing to an existing directory fails after the mocked controller action.
            code, result = self.run_cli(["charge-mode", str(ROOT / "examples/charger-evcc.json"), "smart",
                                        "--expected-mode", "off", "--apply", "--attended", "--out", folder])
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "applied")
            self.assertTrue(result["controller_mode_verified"])
            self.assertIn("receipt_storage_error", result)


if __name__ == "__main__":
    unittest.main()
