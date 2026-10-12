from datetime import datetime, timedelta, timezone
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request

from solar_playbook.metering import (
    MAX_RESPONSE_BYTES, NoMeterRedirect, parse_home_assistant, parse_shelly, read_meter,
)


NOW = datetime(2030, 1, 15, tzinfo=timezone.utc)
ENTITY = "sensor.synthetic_grid_power"


def ha_state(**changes):
    return {"entity_id": ENTITY, "state": "-2500",
            "attributes": {"unit_of_measurement": "W"},
            "last_reported": NOW.isoformat(), **changes}


def fake_opener(payload):
    opener = Mock()
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    opener.open.return_value = io.BytesIO(raw)
    return opener


class MeteringTests(unittest.TestCase):
    def shelly(self, payload=None, **changes):
        args = dict(received_at=NOW, now=NOW, sign="import_positive", phase_count=3)
        return parse_shelly({"id": 0, "total_act_power": -2500} if payload is None else payload,
                            **(args | changes))

    def ha(self, payload=None, **changes):
        args = dict(entity_id=ENTITY, unit="W", received_at=NOW, now=NOW,
                    sign="import_positive")
        return parse_home_assistant(ha_state() if payload is None else payload,
                                    **(args | changes))

    def test_aggregate_shelly_power_units_sign_and_receipt_provenance(self):
        reading = self.shelly()
        self.assertEqual(reading.grid_power_kw, -2.5)
        self.assertEqual(reading.timestamp_quality, "poll_receipt")
        self.assertEqual(reading.timestamp_basis, "local_receipt_not_device_sample")
        self.assertEqual(reading.phase_count, 3)
        self.assertFalse(reading.control_eligible)
        self.assertFalse(reading.hardware_write_performed)
        self.assertEqual(self.shelly(sign="export_positive").grid_power_kw, 2.5)
        self.assertEqual(reading.as_dict()["source"], "shelly_pro3em")

    def test_ha_mapping_uses_exact_entity_unit_and_explicit_sign(self):
        reading = self.ha(sign="export_positive")
        self.assertEqual(reading.grid_power_kw, 2.5)
        state = ha_state(state="3.75", attributes={"unit_of_measurement": "kW"})
        self.assertEqual(self.ha(state, unit="kW").grid_power_kw, 3.75)
        for changes in ({"entity_id": "sensor.other"}, {"unit": "kW"},
                        {"unit": "kWh"}, {"sign": "guess"}, {"sign": None},
                        {"phase_count": True}, {"phase_count": 4}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.ha(**changes)

    def test_ha_timestamp_does_not_certify_device_liveness(self):
        reading = self.ha()
        self.assertEqual(reading.timestamp_quality, "unverified")
        self.assertEqual(reading.timestamp_basis, "home_assistant.last_reported")
        self.assertTrue(reading.is_fresh(NOW))
        self.assertFalse(reading.control_eligible)
        state = ha_state(last_reported=None, last_updated=NOW.isoformat())
        self.assertEqual(self.ha(state).timestamp_basis, "home_assistant.last_updated")
        with self.assertRaises(ValueError):
            self.ha(ha_state(last_reported=None))

    def test_old_and_future_source_timestamps_are_rejected(self):
        for age in (121, -1):
            state = ha_state(last_reported=(NOW - timedelta(seconds=age)).isoformat())
            with self.subTest(age=age), self.assertRaises(ValueError):
                self.ha(state)
        boundary = ha_state(last_reported=(NOW - timedelta(seconds=120)).isoformat())
        self.assertTrue(self.ha(boundary).is_fresh(NOW))
        self.assertFalse(self.ha(boundary).is_fresh(NOW + timedelta(seconds=1)))
        with self.assertRaises(ValueError):
            self.shelly(received_at=NOW - timedelta(seconds=121))
        with self.assertRaises(ValueError):
            self.shelly(received_at=NOW + timedelta(seconds=1))

    def test_unavailable_nonfinite_and_boolean_power_are_rejected(self):
        for value in (None, True, False, "unknown", "unavailable", "nan", "inf", float("nan"),
                      float("inf"), [], {}, 10 ** 1000):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                self.ha(ha_state(state=value))
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                self.shelly({"id": 0, "total_act_power": value})
        with self.assertRaises(ValueError):
            self.shelly({"id": 0, "total_act_power": "1500"})

    def test_shelly_error_status_and_wrong_component_rejected(self):
        for payload in ({"error": {"message": "bad"}}, {"code": 401, "message": "bad"},
                        {"id": 1, "total_act_power": 500},
                        {"id": True, "total_act_power": 500},
                        {"id": 0, "total_act_power": 500, "errors": ["power_meter_failure"]},
                        {"id": 0, "total_act_power": 500, "b_errors": ["out_of_range:active_power"]},
                        {"id": 0, "total_act_power": 500, "errors": None}, []):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.shelly(payload)

    def test_fixture_does_not_refresh_its_recorded_timestamp(self):
        config = {"schema_version": 1, "adapter": "fixture", "source_adapter": "shelly_pro3em",
                  "sign": "import_positive", "received_at": NOW.isoformat(),
                  "payload": {"id": 0, "total_act_power": 3000}}
        reading = read_meter(config, now=NOW)
        self.assertEqual(reading.timestamp_quality, "fixture_receipt")
        self.assertEqual(reading.source, "fixture:shelly_pro3em")
        self.assertEqual(reading.grid_power_kw, 3)
        with self.assertRaises(ValueError):
            read_meter(config, now=NOW + timedelta(minutes=3))
        config.pop("received_at")
        with self.assertRaises(ValueError):
            read_meter(config, now=NOW)

    def test_ha_fixture_does_not_need_credentials_or_transport(self):
        config = {"schema_version": 1, "adapter": "fixture", "source_adapter": "home_assistant",
                  "sign": "import_positive", "received_at": NOW.isoformat(),
                  "entity_id": ENTITY, "unit": "W", "payload": ha_state()}
        opener = Mock()
        reading = read_meter(config, now=NOW, opener=opener)
        opener.open.assert_not_called()
        self.assertEqual(reading.source, "fixture:home_assistant")
        self.assertEqual(reading.timestamp_quality, "unverified")

    def test_shelly_live_client_uses_only_get_status_and_configured_timeout(self):
        opener = fake_opener({"id": 0, "total_act_power": 1500})
        config = {"schema_version": 1, "adapter": "shelly_pro3em", "base_url": "http://shelly.example",
                  "sign": "import_positive", "timeout_seconds": 2}
        result = read_meter(config, now=NOW, opener=opener)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.full_url, "http://shelly.example/rpc/EM.GetStatus?id=0")
        self.assertIsNone(req.get_header("Authorization"))
        self.assertEqual(opener.open.call_args.kwargs, {"timeout": 2})
        self.assertEqual(result.grid_power_kw, 1.5)

    def test_live_receipt_is_recorded_after_response(self):
        opener = fake_opener({"id": 0, "total_act_power": 1000})
        config = {"schema_version": 1, "adapter": "shelly_pro3em", "base_url": "http://shelly.example",
                  "sign": "import_positive"}
        with patch("solar_playbook.metering._utc_now", side_effect=[NOW, NOW + timedelta(seconds=3)]):
            reading = read_meter(config, opener=opener)
        self.assertEqual(reading.received_at, (NOW + timedelta(seconds=3)).isoformat())

    def test_ha_client_token_only_in_header_and_output_has_no_secret(self):
        opener = fake_opener(ha_state())
        config = {"schema_version": 1, "adapter": "home_assistant", "base_url": "https://ha.example",
                  "entity_id": ENTITY, "unit": "W", "sign": "import_positive",
                  "token_env": "TEST_METER_TOKEN"}
        with patch.dict("os.environ", {"TEST_METER_TOKEN": "synthetic-test-token"}):
            reading = read_meter(config, now=NOW, opener=opener)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.get_header("Authorization"), "Bearer synthetic-test-token")
        self.assertNotIn("synthetic-test-token", req.full_url)
        self.assertNotIn("synthetic-test-token", json.dumps(reading.as_dict()))

    def test_auth_network_and_redirect_errors_do_not_echo_response_or_tokens(self):
        config = {"schema_version": 1, "adapter": "home_assistant", "base_url": "https://ha.example",
                  "entity_id": ENTITY, "unit": "W", "sign": "import_positive"}
        for error in (OSError("synthetic-secret"),
                      HTTPError("https://synthetic-secret", 401, "synthetic-secret", {}, None),
                      ValueError("redirect to synthetic-secret")):
            opener = Mock()
            opener.open.side_effect = error
            with patch.dict("os.environ", {"HA_TOKEN": "synthetic-secret"}):
                with self.assertRaises(ValueError) as caught:
                    read_meter(config, now=NOW, opener=opener)
            self.assertNotIn("synthetic-secret", str(caught.exception))
        with self.assertRaises(ValueError):
            NoMeterRedirect().redirect_request(Request("https://ha.example"), None,
                                               302, "moved", {}, "https://other.example")

    def test_invalid_urls_and_header_tokens_fail_before_io(self):
        base = {"schema_version": 1, "adapter": "home_assistant", "entity_id": ENTITY, "unit": "W",
                "sign": "import_positive"}
        for url in ("file:///tmp/data", "http://user:secret@ha.example", "https://ha.example/path",
                    "http://ha.example?", "http://ha.example#", "http://ha.example:bad",
                    "http://ha.example:70000", " http://ha.example", "http://ha.example\n",
                    "http://ha.example/a/..", "http://ha.example\\evil", None):
            opener = Mock()
            with self.subTest(url=url), self.assertRaises(ValueError):
                read_meter(base | {"base_url": url}, now=NOW, opener=opener)
            opener.open.assert_not_called()
        for token in ("", "secret\r\nInjected:value"):
            opener = Mock()
            with patch.dict("os.environ", {"HA_TOKEN": token}), self.assertRaises(ValueError):
                read_meter(base | {"base_url": "http://ha.example"}, now=NOW, opener=opener)
            opener.open.assert_not_called()

    def test_response_size_shape_and_json_numbers_are_bounded(self):
        config = {"schema_version": 1, "adapter": "shelly_pro3em", "base_url": "http://shelly.example",
                  "sign": "import_positive"}
        for payload in (b" " * (MAX_RESPONSE_BYTES + 1), b"[]", b"{bad", b"\xff",
                        b'{"id":0,"total_act_power":NaN}',
                        b'{"id":0,"total_act_power":Infinity}'):
            with self.subTest(length=len(payload)), self.assertRaises(ValueError):
                read_meter(config, now=NOW, opener=fake_opener(payload))

    def test_freshness_policy_requires_aware_clock_and_bounded_age(self):
        for changes in ({"now": NOW.replace(tzinfo=None)}, {"max_age_seconds": 0},
                        {"max_age_seconds": True}, {"max_age_seconds": 3601},
                        {"received_at": NOW.replace(tzinfo=None)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.shelly(**changes)

    def test_config_schema_unknown_keys_and_embedded_credentials_are_rejected(self):
        config = {"schema_version": 1, "adapter": "shelly_pro3em",
                  "base_url": "http://shelly.example", "sign": "import_positive"}
        for changes in ({"schema_version": True}, {"schema_version": 2},
                        {"token": "synthetic-secret"}, {"password": "synthetic-secret"},
                        {"api_key": "synthetic-secret"}, {"sigin": "import_positive"},
                        {"timestamp_quality": "verified"}, {"timeout_seconds": float("nan")},
                        {"timeout_seconds": float("inf")}, {"timeout_seconds": True}):
            opener = Mock()
            with self.subTest(changes=changes), self.assertRaises(ValueError) as caught:
                read_meter(config | changes, now=NOW, opener=opener)
            self.assertNotIn("synthetic-secret", str(caught.exception))
            opener.open.assert_not_called()
        for key in ("schema_version", "adapter", "base_url", "sign"):
            incomplete = dict(config)
            incomplete.pop(key)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                read_meter(incomplete, now=NOW)

    def test_fixture_config_cannot_smuggle_live_connection_settings(self):
        config = {"schema_version": 1, "adapter": "fixture", "source_adapter": "shelly_pro3em",
                  "sign": "import_positive", "received_at": NOW.isoformat(),
                  "payload": {"id": 0, "total_act_power": 1000}}
        for changes in ({"base_url": "http://shelly.example"}, {"token_env": "HA_TOKEN"},
                        {"timeout_seconds": 5}, {"entity_id": "sensor.grid"}):
            opener = Mock()
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                read_meter(config | changes, now=NOW, opener=opener)
            opener.open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
