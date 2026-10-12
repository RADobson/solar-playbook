from dataclasses import replace
from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from solar_playbook.cloud_advisor import AIConfig, AllowanceLedger, advise_cloud, build_request, parse_response
from solar_playbook.demo import scenario
from solar_playbook.planner import plan

NOW = datetime(2030,1,15,tzinfo=timezone.utc)
ADVICE = {"suggested_mode":"balanced", "explanation":"A synthetic schedule that meets the target."}


class CloudAdvisorTests(unittest.TestCase):
    def test_disabled_makes_no_request_and_creates_no_ledger(self):
        with tempfile.TemporaryDirectory() as tmp, patch("solar_playbook.cloud_advisor.build_opener") as opener:
            path = Path(tmp)/"ledger.db"
            answer = advise_cloud(plan(scenario()),AIConfig(),AllowanceLedger(path),NOW)
            self.assertEqual(answer["reason"],"disabled_or_no_plan")
            opener.assert_not_called()
            self.assertFalse(path.exists())

    def test_provider_request_formats_and_no_credentials_in_body(self):
        for provider in ("openai","anthropic","openai_compatible"):
            with self.subTest(provider=provider):
                config = AIConfig(provider=provider,enabled=True,model="test-model",
                                  base_url="https://example.invalid/v1" if provider=="openai_compatible" else "")
                request = build_request({"energy_cost_aud":1},config,"test-only-key")
                self.assertEqual(request.get_method(),"POST")
                self.assertNotIn(b"test-only-key",request.data)
                body = json.loads(request.data)
                self.assertEqual(body["model"],"test-model")
                if provider == "openai":
                    self.assertFalse(body["store"])
                    self.assertTrue(body["text"]["format"]["strict"])
                if provider == "anthropic":
                    self.assertEqual(body["tool_choice"]["name"],"summarise_plan")

    def test_all_provider_response_shapes(self):
        replies = {
            "openai":{"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(ADVICE)}]}]},
            "anthropic":{"stop_reason":"tool_use","content":[{"type":"tool_use","name":"summarise_plan","input":ADVICE}]},
            "openai_compatible":{"choices":[{"finish_reason":"stop","message":{"content":json.dumps(ADVICE)}}]},
        }
        for provider,reply in replies.items():
            with self.subTest(provider=provider):
                self.assertEqual(parse_response(reply,provider),ADVICE)
        with self.assertRaises(ValueError):
            parse_response({"status":"incomplete"},"openai")
        with self.assertRaises(ValueError):
            parse_response({"stop_reason":"max_tokens"},"anthropic")
        with self.assertRaises(ValueError):
            parse_response({"choices":[{"finish_reason":"length"}]},"openai_compatible")

    def test_daily_and_monthly_limits_persist_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"ledger.db"
            config = AIConfig(daily_call_limit=1,monthly_allowance_usd=0.10,reserve_per_call_usd=0.05)
            self.assertTrue(AllowanceLedger(path).reserve(config,NOW))
            self.assertFalse(AllowanceLedger(path).reserve(config,NOW))
            self.assertTrue(AllowanceLedger(path).reserve(config,NOW+timedelta(days=1)))
            self.assertFalse(AllowanceLedger(path).reserve(config,NOW+timedelta(days=2)))
            self.assertTrue(AllowanceLedger(path).reserve(config,NOW+timedelta(days=31)))

    def test_timeout_has_no_retry_and_retains_reservation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ",{"SOLAR_PLAYBOOK_AI_KEY":"test-key"}), patch("solar_playbook.cloud_advisor.build_opener") as opener:
            opener.return_value.open.side_effect = TimeoutError()
            config = AIConfig(provider="openai",enabled=True,model="test-model",daily_call_limit=1)
            ledger = AllowanceLedger(Path(tmp)/"ledger.db")
            report = plan(scenario())
            before = json.dumps(report,sort_keys=True)
            self.assertEqual(advise_cloud(report,config,ledger,NOW)["reason"],"provider_or_ledger_unavailable")
            self.assertEqual(advise_cloud(report,config,ledger,NOW)["reason"],"request_allowance_reached")
            self.assertEqual(opener.return_value.open.call_count,1)
            self.assertEqual(before,json.dumps(report,sort_keys=True))

    def test_cloud_payload_does_not_include_private_inputs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ",{"SOLAR_PLAYBOOK_AI_KEY":"test-key"}), patch("solar_playbook.cloud_advisor.build_opener") as opener:
            body = {"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(ADVICE)}]}]}
            opener.return_value.open.return_value = io.BytesIO(json.dumps(body).encode())
            report = plan(scenario())
            report["private_address"] = "NEVER SEND THIS"
            report["input"]["name"] = "PRIVATE SITE NAME"
            config = AIConfig(provider="openai",enabled=True,model="test-model")
            result = advise_cloud(report,config,AllowanceLedger(Path(tmp)/"ledger.db"),NOW)
            request = opener.return_value.open.call_args.args[0]
            self.assertNotIn(b"NEVER SEND", request.data)
            self.assertNotIn(b"PRIVATE SITE NAME", request.data)
            self.assertNotIn(b"slots", request.data)
            self.assertEqual(result["source"],"openai")

    def test_unsafe_endpoints_and_invalid_allowances(self):
        for config in (AIConfig(provider="openai",base_url="https://other.invalid"),
                       AIConfig(provider="openai_compatible",base_url="http://other.invalid"),
                       AIConfig(provider="openai_compatible",base_url="https://user:pass@example.invalid"),
                       AIConfig(monthly_allowance_usd=float("nan")),AIConfig(daily_call_limit=True)):
            with self.subTest(config=config),self.assertRaises(ValueError):
                config.validate()

    def test_no_feasible_plan_means_no_ai_call(self):
        with tempfile.TemporaryDirectory() as tmp, patch("solar_playbook.cloud_advisor.build_opener") as opener:
            config = AIConfig(provider="openai",enabled=True,model="test-model")
            advise_cloud(plan(scenario("impossible")),config,AllowanceLedger(Path(tmp)/"ledger.db"),NOW)
            opener.assert_not_called()
