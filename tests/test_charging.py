from dataclasses import replace
from datetime import datetime, timezone, timedelta
from http.client import IncompleteRead
import io
import json
import unittest
from unittest.mock import patch

from solar_playbook.charging import ChargerConfig, Evcc, NoRedirect, handoff_mode, parse_state

NOW = datetime(2030, 1, 15, tzinfo=timezone.utc)


def config(**changes):
    return replace(ChargerConfig("http://127.0.0.1:7070", 1, "garage",
                   control_enabled=True, commissioning_id="synthetic",
                   independent_limits_verified=True, fallback_verified=True), **changes)


def state(**point_changes):
    return {"version": "0.317.1", "apiReady": True, "startupCompleted": True,
            "setupRequired": False, "loadpoints": [{"name": "garage", "mode": "off",
            "vehicleName": "", "connected": True, "chargePower": 0, "maxCurrent": 16,
            "phasesConfigured": 1, **point_changes}]}


class Transport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
    def open(self, req, timeout):
        self.requests.append(req)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(json.dumps(response).encode())


class ChargingTests(unittest.TestCase):
    def client(self, cfg, responses, clock=None):
        transport = Transport(responses)
        return Evcc(cfg, opener=transport, clock=clock or (lambda: NOW)), transport

    def test_preview_never_posts_even_if_eligible(self):
        cfg = config()
        client, transport = self.client(cfg, [state()])
        result = handoff_mode(cfg, "smart", expected_mode="off", client=client)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["status"], "preview")
        self.assertEqual([r.get_method() for r in transport.requests], ["GET"])
        self.assertFalse(result["physical_charging_verified"])

    def test_attended_mode_handoff_uses_exact_endpoint_then_verifies(self):
        cfg = config()
        client, transport = self.client(cfg, [state(), "smart", state(mode="smart")])
        result = handoff_mode(cfg, "smart", expected_mode="off", apply=True, attended=True, client=client)
        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["controller_mode_verified"])
        self.assertTrue(result["mode_persists"])
        self.assertFalse(result["physical_charging_verified"])
        self.assertEqual([r.get_method() for r in transport.requests], ["GET", "POST", "GET"])
        self.assertEqual(transport.requests[1].full_url, "http://127.0.0.1:7070/api/loadpoints/1/mode/smart")

    def test_commissioning_attendance_version_and_override_fail_closed(self):
        for changes, payload, attended in [
            ({"control_enabled": False}, state(), True),
            ({"independent_limits_verified": False}, state(), True),
            ({"fallback_verified": False}, state(), True),
            ({"commissioning_id": ""}, state(), True),
            ({"expected_version": "unqualified"}, state(), True),
            ({}, state(), False), ({}, state(mode="now"), True),
            ({}, state(connected=False), True), ({}, state(disabled=True), True),
            ({}, state(maxCurrent=32), True), ({}, state(phasesConfigured=3), True),
            ({"expected_vehicle_name": "car-a"}, state(vehicleName="car-b"), True),
            ({}, dict(state(), apiReady=False), True),
            ({}, dict(state(), startupCompleted=False), True),
        ]:
            with self.subTest(changes=changes, payload=payload):
                cfg = config(**changes)
                client, transport = self.client(cfg, [payload])
                result = handoff_mode(cfg, "smart", expected_mode="off", apply=True, attended=attended, client=client)
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["controller_write_attempted"])
                self.assertEqual(len(transport.requests), 1)

    def test_disallowed_grid_charging_never_posts(self):
        cfg = config()
        client, transport = self.client(cfg, [state()])
        result = handoff_mode(cfg, "now", expected_mode="off", apply=True, attended=True, client=client)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(transport.requests), 1)

    def test_unknown_post_outcome_never_retries(self):
        cfg = config()
        client, transport = self.client(cfg, [state(), OSError("private credential in provider message")])
        result = handoff_mode(cfg, "smart", expected_mode="off", apply=True, attended=True, client=client)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertTrue(result["controller_write_attempted"])
        self.assertNotIn("private credential", json.dumps(result))
        self.assertEqual(len(transport.requests), 2)

    def test_readback_mismatch_or_failure_is_not_success(self):
        for after in (state(mode="off"), state(mode="smart", vehicleName="different-car"), OSError("lost")):
            cfg = config()
            client, _ = self.client(cfg, [state(), "smart", after])
            result = handoff_mode(cfg, "smart", expected_mode="off", apply=True, attended=True, client=client)
            self.assertEqual(result["status"], "unconfirmed")
            self.assertFalse(result["controller_mode_verified"])

    def test_truncated_post_response_is_unconfirmed(self):
        cfg = config()
        client, transport = self.client(cfg, [state(), IncompleteRead(b"private", 50)])
        result = handoff_mode(cfg, "smart", expected_mode="off", apply=True, attended=True, client=client)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(len(transport.requests), 2)
        self.assertNotIn("private", json.dumps(result))

    def test_already_selected_does_not_post(self):
        cfg = config()
        client, transport = self.client(cfg, [state(mode="smart")])
        result = handoff_mode(cfg, "smart", expected_mode="smart", apply=True, attended=True, client=client)
        self.assertEqual(result["status"], "already_selected")
        self.assertEqual(len(transport.requests), 1)

    def test_wrong_client_binding_rejected_before_io(self):
        cfg = config()
        client, transport = self.client(config(base_url="http://another-site.local"), [])
        with self.assertRaises(ValueError):
            handoff_mode(cfg, "smart", expected_mode="off", apply=True, attended=True, client=client)
        self.assertEqual(transport.requests, [])

    def test_expired_preflight_blocks(self):
        cfg = config()
        clock = iter([NOW, NOW + timedelta(seconds=20), NOW + timedelta(seconds=21)])
        client, transport = self.client(cfg, [state()], clock=lambda: next(clock))
        result = handoff_mode(cfg, "smart", expected_mode="off", apply=True, attended=True, client=client)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(transport.requests), 1)

    def test_reject_unknown_identity_and_schema_drift(self):
        for changes in ({"name": "other"}, {"connected": "true"}, {"chargePower": float("nan")},
                        {"maxCurrent": True}, {"phasesConfigured": True}, {"mode": "pv"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_state(state(**changes), config(), received_at=NOW)

    def test_token_is_header_only_and_redirects_refused(self):
        cfg = config(token_env="TEST_EVCC_TOKEN")
        with patch.dict("os.environ", {"TEST_EVCC_TOKEN": "fixture-secret"}):
            client, transport = self.client(cfg, [state()])
            result = client.read()
        self.assertEqual(transport.requests[0].get_header("Authorization"), "Bearer fixture-secret")
        self.assertNotIn("fixture-secret", json.dumps(result.as_dict()))
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, None, None, "http://other/")

    def test_config_rejects_credentials_unknown_fields_versions_and_types(self):
        good = {"schema_version": 1, "adapter": "evcc", "base_url": "http://localhost:7070",
                "loadpoint_id": 1, "expected_loadpoint_name": "garage"}
        for delta in ({"schema_version": 2}, {"schema_version": True}, {"token": "secret"},
                      {"base_url": "http://user:password@host"}, {"loadpoint_id": True},
                      {"control_enabled": "false"}, {"phases": 0}, {"max_current_amps": float("nan")}):
            with self.subTest(delta=delta), self.assertRaises((ValueError, TypeError)):
                ChargerConfig.from_dict(good | delta)


if __name__ == "__main__":
    unittest.main()
