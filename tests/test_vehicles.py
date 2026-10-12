from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from solar_playbook.demo import scenario
from solar_playbook.planner import plan
from solar_playbook.vehicles import resolve_vehicle_request


NOW = datetime(2030, 1, 15, tzinfo=timezone.utc)


def add_energy(**changes):
    return {"schema_version": 1, "mode": "add_energy", "energy_kwh": 15,
            "energy_basis": "wall", "charging_efficiency": 0.9} | changes


def soc_request(**changes):
    return {"schema_version": 1, "mode": "target_soc", "target_soc_percent": 80,
            "capacity_kwh": 60, "capacity_basis": "usable", "charging_efficiency": 0.9,
            "telemetry": {"source": "home_assistant", "entity_id": "sensor.car_soc",
                          "timestamp_field": "attributes.vehicle_observed_at", "max_age_seconds": 600}} | changes


def soc_state(**changes):
    return {"entity_id": "sensor.car_soc", "state": "50",
            "attributes": {"unit_of_measurement": "%", "vehicle_observed_at": NOW.isoformat()},
            "last_reported": NOW.isoformat()} | changes


class VehicleTests(unittest.TestCase):
    def test_offline_wall_energy_converts_to_battery_and_preserves_planner_units(self):
        result = resolve_vehicle_request(add_energy(), now=NOW)
        self.assertEqual(result.required_battery_kwh, 13.5)
        self.assertEqual(result.quality, "estimated_conversion")
        demo = scenario()
        demo = replace(demo, ev_required_kwh=result.required_battery_kwh,
                       site=replace(demo.site, ev_efficiency=result.charging_efficiency))
        selected = plan(demo)["selected"]
        self.assertIsNotNone(selected)
        wall_kwh = sum(row["ev_ac_kw"] for row in selected["rows"]) * demo.slot_minutes / 60
        self.assertGreaterEqual(wall_kwh, 15)
        self.assertAlmostEqual(selected["ev_added_kwh"], wall_kwh * 0.9)

    def test_battery_energy_not_discounted_twice(self):
        result = resolve_vehicle_request(add_energy(energy_basis="battery"), now=NOW)
        self.assertEqual(result.required_battery_kwh, 15)

    def test_fresh_source_soc_yields_estimate_and_provenance(self):
        result = resolve_vehicle_request(soc_request(), now=NOW, state=soc_state())
        self.assertEqual(result.required_battery_kwh, 18)
        self.assertEqual(result.provenance["timestamp_basis"], "mapped_source_observation")
        self.assertEqual(result.provenance["capacity_basis"], "usable")
        self.assertEqual(result.quality, "estimated_soc_energy")
        json.dumps(asdict(result), allow_nan=False)

    def test_nominal_capacity_is_explicit_and_labelled_estimate(self):
        result = resolve_vehicle_request(soc_request(capacity_basis="nominal"), now=NOW, state=soc_state())
        self.assertEqual(result.provenance["capacity_basis"], "nominal")
        self.assertIn("nominal", " ".join(result.assumptions))
        self.assertIn("estimate", result.quality)

    def test_target_at_or_below_current_does_not_request_discharge(self):
        for target in (0, 40, 50):
            with self.subTest(target=target):
                result = resolve_vehicle_request(soc_request(target_soc_percent=target), now=NOW, state=soc_state())
                self.assertEqual(result.required_battery_kwh, 0)

    def test_stale_or_future_vehicle_time_is_not_masked_by_fresh_ha_poll(self):
        for delta in (-601, 1):
            state = soc_state()
            state["attributes"]["vehicle_observed_at"] = (NOW + timedelta(seconds=delta)).isoformat()
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                resolve_vehicle_request(soc_request(), now=NOW, state=state)

    def test_ha_timestamp_only_is_marked_lower_quality(self):
        config = soc_request()
        config["telemetry"]["timestamp_field"] = "last_reported"
        result = resolve_vehicle_request(config, now=NOW, state=soc_state())
        self.assertEqual(result.quality, "estimated_soc_energy_ha_timestamp_only")
        self.assertTrue(any("does not prove" in note for note in result.assumptions))

    def test_rejects_unknown_nonfinite_boolean_and_out_of_range_soc(self):
        for value in (None, True, False, "unavailable", "unknown", "nan", "inf", float("nan"), -1, 101, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_vehicle_request(soc_request(), now=NOW, state=soc_state(state=value))

    def test_requires_percent_units_matching_entity_and_explicit_timestamp(self):
        cases = [soc_state(entity_id="sensor.other"), soc_state(attributes={}),
                 soc_state(attributes={"unit_of_measurement": "fraction", "vehicle_observed_at": NOW.isoformat()}),
                 soc_state(attributes={"unit_of_measurement": "%", "vehicle_observed_at": "2030-01-15T00:00:00"}),
                 soc_state(attributes=None)]
        for state in cases:
            with self.subTest(state=state), self.assertRaises(ValueError):
                resolve_vehicle_request(soc_request(), now=NOW, state=state)

    def test_unavailable_api_never_infers_target_and_redacts_failure(self):
        client = Mock()
        client.state.side_effect = OSError("private upstream response")
        with self.assertRaisesRegex(ValueError, "telemetry unavailable") as raised:
            resolve_vehicle_request(soc_request(), now=NOW, client=client)
        self.assertNotIn("private", str(raised.exception))
        client.state.assert_called_once_with("sensor.car_soc")

    def test_configured_ha_reads_only_mapped_entity_with_token_from_environment(self):
        config = soc_request()
        config["telemetry"].update(base_url="http://homeassistant.local:8123", token_env="TEST_VEHICLE_TOKEN")
        with patch.dict("os.environ", {"TEST_VEHICLE_TOKEN": "secret-value"}), \
             patch("solar_playbook.vehicles.HomeAssistant") as ha:
            ha.return_value.state.return_value = soc_state()
            result = resolve_vehicle_request(config, now=NOW)
        ha.assert_called_with("http://homeassistant.local:8123", "secret-value")
        ha.return_value.state.assert_called_once_with("sensor.car_soc")
        self.assertNotIn("secret-value", json.dumps(asdict(result)))

    def test_missing_token_does_not_attempt_network(self):
        config = soc_request()
        config["telemetry"].update(base_url="http://homeassistant.local:8123", token_env="UNSET_VEHICLE_TOKEN")
        with patch.dict("os.environ", {}, clear=True), patch("solar_playbook.vehicles.HomeAssistant.state") as state:
            with self.assertRaisesRegex(ValueError, "environment variable is missing"):
                resolve_vehicle_request(config, now=NOW)
            state.assert_not_called()

    def test_strict_config_rejects_ambiguous_secrets_units_and_bounds(self):
        configs = [add_energy(token="secret"), add_energy(energy_basis="kWh"), add_energy(energy_kwh=True),
                   add_energy(energy_kwh=float("inf")), add_energy(energy_kwh=201), add_energy(energy_kwh=-1),
                   add_energy(energy_kwh=10 ** 400),
                   add_energy(charging_efficiency=0), add_energy(charging_efficiency=True),
                   add_energy(charging_efficiency=1.1), add_energy(schema_version=True),
                   soc_request(capacity_basis="gross"), soc_request(capacity_kwh=0),
                   soc_request(capacity_kwh=201), soc_request(target_soc_percent=True),
                   soc_request(target_soc_percent=101), soc_request(telemetry=None)]
        for config in configs:
            with self.subTest(config=config), self.assertRaises(ValueError):
                resolve_vehicle_request(config, now=NOW)
        for update in ({"token": "secret"}, {"max_age_seconds": True}, {"max_age_seconds": 3601},
                       {"timestamp_field": "state"}, {"entity_id": "sensor.bad/path"},
                       {"source": "byd_cloud"}, {"base_url": "http://ha"},
                       {"base_url": "http://user:password@ha", "token_env": "TOKEN"},
                       {"base_url": "http://ha", "token_env": "not a name"}):
            config = soc_request()
            config["telemetry"].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                resolve_vehicle_request(config, now=NOW, state=soc_state())

    def test_aware_clock_and_injection_contract_are_required(self):
        for now in ("2030-01-15", NOW.replace(tzinfo=None)):
            with self.subTest(now=now), self.assertRaises(ValueError):
                resolve_vehicle_request(add_energy(), now=now)
        with self.assertRaises(ValueError):
            resolve_vehicle_request(soc_request(), now=NOW, state=soc_state(), client=Mock())
        with self.assertRaises(ValueError):
            resolve_vehicle_request(add_energy(), now=NOW, state=soc_state())

    def test_live_clock_is_captured_after_blocking_read(self):
        class Clock(datetime):
            current = NOW

            @classmethod
            def now(cls, tz=None):
                return cls.current.astimezone(tz)

        def fetch(entity_id):
            Clock.current = NOW + timedelta(seconds=2)
            state = soc_state()
            state["attributes"]["vehicle_observed_at"] = Clock.current.isoformat()
            return state

        client = Mock()
        client.state.side_effect = fetch
        with patch("solar_playbook.vehicles.datetime", Clock):
            result = resolve_vehicle_request(soc_request(), client=client)
        self.assertEqual(result.required_battery_kwh, 18)
        self.assertEqual(result.provenance["age_seconds"], 0)
        # An explicit replay clock must not silently advance to wall time.
        with self.assertRaisesRegex(ValueError, "future"):
            resolve_vehicle_request(soc_request(), now=NOW, client=client)

    def test_offline_example_needs_no_car_api_or_network(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "examples/vehicle-offline.json").read_text())
        with patch("solar_playbook.vehicles.HomeAssistant") as ha:
            result = resolve_vehicle_request(config, now=NOW)
        ha.assert_not_called()
        self.assertEqual(result.required_battery_kwh, 13.5)


if __name__ == "__main__":
    unittest.main()
