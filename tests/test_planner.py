from dataclasses import replace
from datetime import timedelta
import math
import random
import unittest

from solar_playbook.demo import scenario
from solar_playbook.model import Scenario, timestamp
from solar_playbook.planner import plan, simulate


class PlannerTests(unittest.TestCase):
    def test_sunny_cloudy_away_meet_deadline(self):
        for name in ("sunny", "cloudy", "away"):
            with self.subTest(name=name):
                case = scenario(name)
                result = plan(case)
                self.assertEqual(result["status"], "ready")
                self.assertGreaterEqual(result["selected"]["ev_added_kwh"], case.ev_required_kwh)
                for row, slot in zip(result["selected"]["rows"], case.slots):
                    if not slot.ev_available:
                        self.assertEqual(row["ev_amps"], 0)
                    if timestamp(slot.start) >= timestamp(case.ev_deadline):
                        self.assertEqual(row["ev_amps"], 0)

    def test_impossible_target_has_no_selected_plan(self):
        self.assertEqual(plan(scenario("impossible"))["status"], "no_feasible_candidate")
        self.assertIsNone(plan(scenario("impossible"))["selected"])

    def test_stale_forecast_is_not_scheduled(self):
        self.assertEqual(plan(scenario("stale"))["status"], "stale_forecast")

    def test_no_available_vehicle(self):
        case = scenario()
        case = replace(case, slots=tuple(replace(s, ev_available=False) for s in case.slots))
        self.assertIsNone(plan(case)["selected"])

    def test_zero_target_never_charges_even_at_negative_prices(self):
        case = scenario()
        case = replace(case, ev_required_kwh=0,
                       slots=tuple(replace(s, import_aud_per_kwh=-0.5) for s in case.slots))
        self.assertEqual(plan(case)["selected"]["ev_added_kwh"], 0)

    def test_dc_surplus_charges_battery_beyond_ac_rating(self):
        case = scenario()
        slot = replace(case.slots[0], pv_dc_kw=18, home_kw=10, ev_available=False)
        case = replace(case, slots=(slot,), ev_required_kwh=0,
                       ev_deadline=(timestamp(slot.start)+timedelta(minutes=30)).isoformat())
        row = simulate(case, [0])["rows"][0]
        self.assertAlmostEqual(row["pv_ac_kw"], 10)
        self.assertGreater(row["battery_charge_dc_kw"], 7)
        self.assertEqual(row["curtailed_dc_kw"], 0)

    def test_full_battery_clips_when_ac_export_limited(self):
        case = scenario()
        case = replace(case, site=replace(case.site, initial_battery_kwh=20), ev_required_kwh=0,
                       slots=tuple(replace(s, pv_dc_kw=18, home_kw=1) for s in case.slots))
        row = simulate(case, [0]*48)["rows"][0]
        self.assertEqual(row["battery_charge_dc_kw"], 0)
        self.assertGreater(row["curtailed_dc_kw"], 10)

    def test_ev_protection_holds_entire_battery(self):
        case = scenario()
        row = simulate(case, [6]+[0]*47)["rows"][0]
        self.assertEqual(row["battery_discharge_dc_kw"], 0)
        self.assertGreater(row["grid_import_kw"], 0)

    def test_grid_limit_failure(self):
        case = scenario()
        case = replace(case, site=replace(case.site, grid_import_limit_kw=0),
                       slots=tuple(replace(s, pv_dc_kw=0) for s in case.slots))
        self.assertIsNone(plan(case)["selected"])

    def test_invalid_currents_are_rejected(self):
        for amps in (-1, 1, 5, 33, 6.1, True):
            with self.subTest(amps=amps), self.assertRaises(ValueError):
                simulate(scenario(), [amps]+[0]*47)

    def test_invalid_input_contract(self):
        case = scenario()
        for value in (float("nan"), float("inf"), -1, 19, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(case, slots=(replace(case.slots[0], pv_dc_kw=value),)+case.slots[1:]).validate()
        with self.assertRaises(ValueError):
            replace(case, slots=case.slots[::-1]).validate()
        with self.assertRaises(ValueError):
            replace(case, site=replace(case.site, reserve_kwh=21)).validate()
        with self.assertRaises(ValueError):
            timestamp("2030-01-15T00:00:00")

    def test_energy_conservation_random_days(self):
        rng = random.Random(140)
        for _ in range(20):
            case = scenario()
            case = replace(case, ev_required_kwh=0, slots=tuple(
                replace(slot, pv_dc_kw=rng.uniform(0,18), home_kw=rng.uniform(0,12))
                for slot in case.slots))
            result = simulate(case, [0]*48)
            s, dt = case.site, 0.5
            for row in result["rows"]:
                # Independent checks of the three conservation equations.
                self.assertAlmostEqual(row["pv_dc_kw"], row["pv_to_ac_dc_kw"] +
                    row["battery_charge_dc_kw"] + row["grid_export_kw"]/s.inverter_efficiency + row["curtailed_dc_kw"])
                self.assertAlmostEqual(row["pv_ac_kw"]+row["battery_ac_kw"]+row["grid_import_kw"], row["home_kw"]+row["ev_ac_kw"])
                self.assertAlmostEqual(row["battery_after_kwh"]-row["battery_before_kwh"], dt*(
                    row["battery_charge_dc_kw"]*s.battery_charge_efficiency - row["battery_discharge_dc_kw"]/s.battery_discharge_efficiency))
                self.assertGreaterEqual(row["battery_after_kwh"], s.reserve_kwh-1e-7)
                self.assertLessEqual(row["battery_after_kwh"], s.battery_kwh+1e-7)
                self.assertLessEqual(row["pv_ac_kw"]+row["battery_ac_kw"]+row["grid_export_kw"], s.inverter_ac_kw+1e-7)
                self.assertLessEqual(row["battery_charge_dc_kw"]*row["battery_discharge_dc_kw"], 1e-7)
                self.assertLessEqual(row["grid_import_kw"]*row["grid_export_kw"], 1e-7)

    def test_selects_lowest_feasible_score(self):
        result = plan(scenario())
        self.assertEqual(result["selected"]["score_aud"], min(c["score_aud"] for c in result["candidates"] if c["feasible"]))

    def test_non_boundary_deadline_never_runs_past_it(self):
        case = scenario()
        case = replace(case, ev_deadline=case.ev_deadline.replace("23:00", "22:15"))
        rows = plan(case)["selected"]["rows"]
        for row in rows:
            if row["ev_amps"]:
                self.assertLessEqual(timestamp(row["start"])+timedelta(minutes=30), timestamp(case.ev_deadline))
