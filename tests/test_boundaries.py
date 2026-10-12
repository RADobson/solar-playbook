from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree.ElementTree import ParseError
from unittest.mock import patch

from solar_playbook.advisor import advise, validate_advice
from solar_playbook.cli import main
from solar_playbook.demo import scenario
from solar_playbook.forecast import parse_bom_xml, weather_is_fresh
from solar_playbook.home_assistant import HomeAssistant, numeric_state, proposal_gate
from solar_playbook.planner import plan
from solar_playbook.report import render

NOW = datetime(2030,1,15,0,0,tzinfo=timezone.utc)
XML = '''<product><amoc><issue-time-utc>2030-01-14T23:00:00Z</issue-time-utc></amoc>
<forecast><area aac="TEST" description="Synthetic fixture"><forecast-period
start-time-utc="2030-01-15T00:00:00Z" end-time-utc="2030-01-16T00:00:00Z">
<text type="precis">Synthetic cloudy day</text><text type="probability_of_precipitation">70%</text>
</forecast-period></area></forecast></product>'''


class BoundaryTests(unittest.TestCase):
    def test_bom_context_not_solar_power(self):
        context = parse_bom_xml(XML, "TEST")
        self.assertEqual(context["role"], "weather_context_only")
        self.assertEqual(context["periods"][0]["values"]["probability_of_precipitation"], "70%")
        self.assertTrue(weather_is_fresh(context, NOW))
        self.assertFalse(weather_is_fresh(context, NOW+timedelta(hours=13)))
        self.assertFalse(weather_is_fresh(context, NOW-timedelta(hours=2)))

    def test_bom_missing_area_or_entity_declaration(self):
        for xml, area in ((XML,"UNKNOWN"),("<!DOCTYPE a>"+XML,"TEST"),("<bad", "TEST")):
            with self.subTest(area=area), self.assertRaises((ValueError, ParseError)):
                parse_bom_xml(xml, area)

    def test_advisor_rejects_commands_and_excess_fields(self):
        for value in ({"suggested_mode":"disable_reserve","explanation":"x"},
                      {"suggested_mode":"balanced","explanation":"x","command":"start"},
                      {"suggested_mode":"balanced","explanation":"x"*1201}):
            with self.assertRaises(ValueError):
                validate_advice(value)

    def test_ollama_outage_keeps_plan(self):
        report = plan(scenario())
        before = json.dumps(report, sort_keys=True)
        with patch("solar_playbook.advisor.urlopen", side_effect=OSError("offline")):
            self.assertEqual(advise(report)["source"], "fallback")
        self.assertEqual(before, json.dumps(report, sort_keys=True))

    def test_valid_model_output_is_only_advice(self):
        report = plan(scenario())
        raw = json.dumps({"message":{"content":json.dumps({"suggested_mode":"solar_first","explanation":"Use daylight."})}}).encode()
        with patch("solar_playbook.advisor.urlopen", return_value=io.BytesIO(raw)):
            result = advise(report)
        self.assertEqual(result["source"], "ollama")
        self.assertNotIn("command", result)

    def test_ha_unknown_nan_wrong_unit_and_stale_fail(self):
        good = {"state":"5.0", "attributes":{"unit_of_measurement":"kW"},"last_reported":NOW.isoformat()}
        self.assertEqual(numeric_state(good, unit="kW", now=NOW), 5)
        for bad in (dict(good,state="unavailable"),dict(good,state="nan"),
                    dict(good,attributes={"unit_of_measurement":"W"}),
                    dict(good,last_reported=(NOW-timedelta(minutes=3)).isoformat())):
            with self.assertRaises(ValueError):
                numeric_state(bad, unit="kW", now=NOW)

    def test_ha_request_is_authenticated_get(self):
        fake = {"entity_id":"sensor.example","state":"42"}
        with patch("solar_playbook.home_assistant.build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps(fake).encode())
            self.assertEqual(HomeAssistant("http://127.0.0.1:8123","test-token").state("sensor.example"), fake)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_ha_rejects_credentials_in_url(self):
        with self.assertRaises(ValueError):
            HomeAssistant("http://user:password@example.com", "test-token")

    def gate_args(self):
        return dict(now=NOW,valid_from=NOW.isoformat(),valid_until=(NOW+timedelta(seconds=60)).isoformat(),
                    observed_at=NOW.isoformat(),manual_override=False,home=True,plugged_in=True,
                    commissioned=True,requested_amps=16)

    def test_proposal_gate_expiry_override_and_disconnect(self):
        good = self.gate_args()
        self.assertTrue(proposal_gate(**good)["eligible"])
        for change in ({"manual_override":True},{"home":False},{"plugged_in":False},{"commissioned":False},
                       {"requested_amps":33},{"requested_amps":True},
                       {"valid_until":NOW.isoformat()},
                       {"observed_at":(NOW-timedelta(seconds=91)).isoformat()}):
            with self.subTest(change=change):
                result = proposal_gate(**(good|change))
                self.assertFalse(result["eligible"])
                self.assertFalse(result["hardware_write_performed"])

    def test_report_escapes_text(self):
        report = plan(scenario())
        report["scenario"] = '<script>alert(1)</script>'
        html = render(report)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_cli_generates_replayable_report(self):
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO):
            path = Path(tmp)
            self.assertEqual(main(["demo","--out",str(path)]),0)
            self.assertTrue((path/"report.html").is_file())
            self.assertEqual(main(["plan",str(path/"input.json"),"--out",str(path/"replay")]),0)
            self.assertEqual(json.loads((path/"report.json").read_text()), json.loads((path/"replay/report.json").read_text()))
            self.assertEqual(main(["demo","--scenario","impossible","--out",str(path/"impossible")]),2)


if __name__ == "__main__":
    unittest.main()
