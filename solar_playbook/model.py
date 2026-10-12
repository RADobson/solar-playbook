"""Small, explicit input contract. Powers are interval averages, never energy."""
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from math import isfinite


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamps must be strings")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("timestamps must include a UTC offset")
    return result


def finite(value: float, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")


@dataclass(frozen=True)
class Site:
    # Example defaults are a hypothetical site, not a manufacturer's specification.
    pv_dc_limit_kw: float = 18.0
    inverter_ac_kw: float = 10.0
    battery_kwh: float = 20.0
    initial_battery_kwh: float = 8.0
    reserve_kwh: float = 4.0
    battery_charge_dc_kw: float = 8.0
    battery_discharge_dc_kw: float = 8.0
    inverter_efficiency: float = 0.96
    battery_charge_efficiency: float = 0.97
    battery_discharge_efficiency: float = 0.97
    ev_efficiency: float = 0.90
    voltage: float = 230.0
    ev_min_amps: int = 6
    ev_max_amps: int = 32
    grid_import_limit_kw: float = 15.0
    grid_export_limit_kw: float = 5.0
    battery_wear_aud_per_kwh: float = 0.03
    terminal_energy_value_aud_per_kwh: float = 0.15
    protect_battery_while_ev_charging: bool = True

    def validate(self) -> None:
        for field in fields(self):
            if field.name == "protect_battery_while_ev_charging":
                if not isinstance(getattr(self, field.name), bool):
                    raise ValueError("battery protection must be boolean")
                continue
            value = getattr(self, field.name)
            finite(value, field.name)
            if value < 0:
                raise ValueError(f"{field.name} cannot be negative")
        if not 0 <= self.reserve_kwh <= self.initial_battery_kwh <= self.battery_kwh:
            raise ValueError("require reserve <= initial battery <= capacity")
        if self.battery_kwh <= 0 or self.inverter_ac_kw <= 0 or self.voltage <= 0:
            raise ValueError("capacity, inverter rating and voltage must be positive")
        for name in ("inverter_efficiency", "battery_charge_efficiency",
                     "battery_discharge_efficiency", "ev_efficiency"):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if any(type(x) is not int for x in (self.ev_min_amps, self.ev_max_amps)):
            raise ValueError("EV amp limits must be integers")
        if not 6 <= self.ev_min_amps <= self.ev_max_amps <= 80:
            raise ValueError("require 6 <= minimum EV amps <= maximum <= 80")


@dataclass(frozen=True)
class Slot:
    start: str
    pv_dc_kw: float
    home_kw: float
    import_aud_per_kwh: float
    export_aud_per_kwh: float = 0.0
    ev_available: bool = True

    def validate(self, site: Site) -> None:
        timestamp(self.start)
        for name in ("pv_dc_kw", "home_kw", "import_aud_per_kwh", "export_aud_per_kwh"):
            finite(getattr(self, name), name)
        if not 0 <= self.pv_dc_kw <= site.pv_dc_limit_kw:
            raise ValueError("PV power outside configured DC range")
        if self.home_kw < 0 or type(self.ev_available) is not bool:
            raise ValueError("invalid home load or EV availability")


@dataclass(frozen=True)
class Scenario:
    name: str
    generated_at: str
    slot_minutes: int
    ev_required_kwh: float
    ev_deadline: str
    site: Site
    slots: tuple[Slot, ...]

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        data = dict(data)
        data["site"] = Site(**data["site"])
        data["slots"] = tuple(Slot(**slot) for slot in data["slots"])
        result = cls(**data)
        result.validate()
        return result

    def validate(self) -> None:
        self.site.validate()
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 120:
            raise ValueError("scenario name must contain 1 to 120 characters")
        timestamp(self.generated_at)
        deadline = timestamp(self.ev_deadline)
        finite(self.ev_required_kwh, "ev_required_kwh")
        if self.ev_required_kwh < 0 or self.ev_required_kwh > 200:
            raise ValueError("EV target must be in [0, 200] kWh")
        if self.slot_minutes not in (15, 30, 60) or type(self.slot_minutes) is not int:
            raise ValueError("use 15, 30 or 60 minute intervals")
        if not 1 <= len(self.slots) <= 192:
            raise ValueError("use between 1 and 192 slots")
        start = timestamp(self.slots[0].start)
        step = timedelta(minutes=self.slot_minutes)
        for i, slot in enumerate(self.slots):
            slot.validate(self.site)
            if timestamp(slot.start) != start + i * step:
                raise ValueError("forecast slots must be contiguous and equally spaced")
        if not start < deadline <= start + len(self.slots) * step:
            raise ValueError("EV deadline must fall within the horizon")
        if timestamp(self.generated_at) > start:
            raise ValueError("forecast issue time cannot follow horizon start")
