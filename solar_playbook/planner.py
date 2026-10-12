"""Finite candidate search with a DC-coupled energy-flow simulator.

This is an explainable reference planner, not a global mathematical optimiser.
Battery operation is modelled as self-consumption with an optional EV hold.
No function in this module communicates with real equipment.
"""
from dataclasses import asdict
from datetime import timedelta
from math import ceil, floor

from .model import Scenario, timestamp

EPS = 1e-7


def simulate(scenario: Scenario, amps: list[int]) -> dict:
    scenario.validate()
    s = scenario.site
    dt = scenario.slot_minutes / 60
    if len(amps) != len(scenario.slots):
        raise ValueError("schedule length does not match horizon")
    battery = s.initial_battery_kwh
    rows, violations = [], []
    for slot, current in zip(scenario.slots, amps):
        if type(current) is not int or (current != 0 and not s.ev_min_amps <= current <= s.ev_max_amps):
            raise ValueError("invalid EV current")
        end = timestamp(slot.start) + timedelta(minutes=scenario.slot_minutes)
        if current and (not slot.ev_available or end > timestamp(scenario.ev_deadline)):
            raise ValueError("EV scheduled outside availability/deadline")
        ev = current * s.voltage / 1000
        demand = slot.home_kw + ev
        before = battery
        # Serve AC loads, respecting the shared inverter limit.
        pv_ac_dc = min(slot.pv_dc_kw, demand / s.inverter_efficiency,
                       s.inverter_ac_kw / s.inverter_efficiency)
        pv_ac = pv_ac_dc * s.inverter_efficiency
        remaining_dc = slot.pv_dc_kw - pv_ac_dc
        charge_dc = min(remaining_dc, s.battery_charge_dc_kw,
                        (s.battery_kwh - battery) / (dt * s.battery_charge_efficiency))
        charge_dc = max(0.0, charge_dc)
        battery += charge_dc * dt * s.battery_charge_efficiency
        remaining_dc -= charge_dc
        discharge_dc = 0.0
        if charge_dc < EPS and not (current and s.protect_battery_while_ev_charging):
            discharge_dc = max(0.0, min(
                (demand - pv_ac) / s.inverter_efficiency,
                s.battery_discharge_dc_kw,
                (battery - s.reserve_kwh) * s.battery_discharge_efficiency / dt,
                (s.inverter_ac_kw - pv_ac) / s.inverter_efficiency,
            ))
        battery -= discharge_dc * dt / s.battery_discharge_efficiency
        battery_ac = discharge_dc * s.inverter_efficiency
        grid_import = max(0.0, demand - pv_ac - battery_ac)
        # Only surplus PV can be exported; no battery export or grid charging.
        export_ac = min(remaining_dc * s.inverter_efficiency,
                        max(0.0, s.inverter_ac_kw - pv_ac - battery_ac),
                        s.grid_export_limit_kw)
        curtailed_dc = max(0.0, remaining_dc - export_ac / s.inverter_efficiency)
        if grid_import > s.grid_import_limit_kw + EPS:
            violations.append(f"{slot.start}: grid import exceeds site limit")
        cost = dt * (grid_import * slot.import_aud_per_kwh - export_ac * slot.export_aud_per_kwh)
        rows.append({
            "start": slot.start, "pv_dc_kw": slot.pv_dc_kw, "home_kw": slot.home_kw,
            "ev_amps": current, "ev_ac_kw": ev,
            "pv_to_ac_dc_kw": pv_ac_dc, "pv_ac_kw": pv_ac,
            "battery_charge_dc_kw": charge_dc, "battery_discharge_dc_kw": discharge_dc,
            "battery_ac_kw": battery_ac, "battery_before_kwh": before,
            "battery_after_kwh": battery, "grid_import_kw": grid_import,
            "grid_export_kw": export_ac, "curtailed_dc_kw": curtailed_dc,
            "energy_cost_aud": cost,
        })
    ev_added = sum(row["ev_ac_kw"] for row in rows) * dt * s.ev_efficiency
    if ev_added + EPS < scenario.ev_required_kwh:
        violations.append("EV energy target not met by deadline")
    # Upper bound allows only quantisation at the minimum current / final interval.
    quantum = s.voltage / 1000 * dt * s.ev_efficiency
    if ev_added > scenario.ev_required_kwh + s.ev_min_amps * quantum + EPS:
        violations.append("EV energy target overshot beyond interval tolerance")
    cost = sum(row["energy_cost_aud"] for row in rows)
    throughput = sum(row["battery_charge_dc_kw"] + row["battery_discharge_dc_kw"] for row in rows) * dt
    # Compare plans with different ending battery levels on an explicit common basis.
    terminal_adjustment = (s.initial_battery_kwh - battery) * s.terminal_energy_value_aud_per_kwh
    return {
        "feasible": not violations, "violations": violations, "rows": rows,
        "energy_cost_aud": cost, "ev_added_kwh": ev_added,
        "ending_battery_kwh": battery, "battery_throughput_kwh": throughput,
        "curtailed_kwh": sum(row["curtailed_dc_kw"] for row in rows) * dt,
        "import_kwh": sum(row["grid_import_kw"] for row in rows) * dt,
        "export_kwh": sum(row["grid_export_kw"] for row in rows) * dt,
        "score_aud": cost + throughput * s.battery_wear_aud_per_kwh + terminal_adjustment,
        "terminal_adjustment_aud": terminal_adjustment,
    }


def _allocate(scenario: Scenario, strategy: str) -> list[int]:
    s = scenario.site
    dt = scenario.slot_minutes / 60
    quantum = s.voltage / 1000 * dt * s.ev_efficiency
    remaining = ceil(scenario.ev_required_kwh / quantum - EPS)
    amps = [0] * len(scenario.slots)
    capacities = {}
    scores = {}
    for i, slot in enumerate(scenario.slots):
        end = timestamp(slot.start) + timedelta(minutes=scenario.slot_minutes)
        if not slot.ev_available or end > timestamp(scenario.ev_deadline):
            continue
        pv_ac = min(slot.pv_dc_kw * s.inverter_efficiency, s.inverter_ac_kw)
        # Conservative allocation ignores battery support while charging.
        capacity = min(s.ev_max_amps, floor((pv_ac + s.grid_import_limit_kw - slot.home_kw)
                                            * 1000 / s.voltage + EPS))
        if capacity < s.ev_min_amps:
            continue
        capacities[i] = capacity
        surplus = max(0.0, pv_ac - slot.home_kw)
        grid_fraction = 1 - min(1, surplus / (capacity * s.voltage / 1000))
        if strategy == "solar_first":
            score = (-surplus, slot.import_aud_per_kwh, i)
        elif strategy == "tariff_first":
            score = (slot.import_aud_per_kwh, -surplus, i)
        elif strategy == "balanced":
            # Opportunity cost of consuming PV that could have been exported.
            score = (grid_fraction * slot.import_aud_per_kwh +
                     (1 - grid_fraction) * slot.export_aud_per_kwh, i)
        elif strategy == "early":
            score = (i,)
        elif strategy == "late":
            score = (-i,)
        else:
            raise ValueError("unknown strategy")
        scores[i] = score
    for i in sorted(scores, key=scores.get):
        if remaining <= 0:
            break
        value = min(capacities[i], max(s.ev_min_amps, remaining))
        amps[i] = value
        remaining -= value
    return amps


def plan(scenario: Scenario, *, forecast_max_age_hours: float = 12) -> dict:
    scenario.validate()
    age = (timestamp(scenario.slots[0].start) - timestamp(scenario.generated_at)).total_seconds() / 3600
    if age > forecast_max_age_hours:
        return {"status": "stale_forecast", "selected": None, "candidates": [],
                "message": "Forecast is too old. Use the household's native fallback schedule."}
    candidates = []
    for strategy in ("balanced", "solar_first", "tariff_first", "early", "late"):
        result = simulate(scenario, _allocate(scenario, strategy))
        result["strategy"] = strategy
        candidates.append(result)
    feasible = [candidate for candidate in candidates if candidate["feasible"]]
    selected = min(feasible, key=lambda c: c["score_aud"]) if feasible else None
    return {
        "schema_version": 1, "mode": "simulation", "scenario": scenario.name,
        "status": "ready" if selected else "no_feasible_candidate",
        "message": ("Lowest modelled score among five candidate schedules; no global optimality claim."
                    if selected else "No tested candidate meets the constraints; notify owner and retain native control."),
        "input": asdict(scenario), "selected": selected, "candidates": candidates,
    }
