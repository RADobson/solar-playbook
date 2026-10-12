"""Provider-neutral input boundary and BoM XML weather-context parser.

BoM context is deliberately not converted into invented solar kW estimates.
No real BoM data is bundled or redistributed by this project.
"""
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from .model import timestamp


def parse_bom_xml(xml: str, area_aac: str) -> dict:
    if len(xml.encode("utf-8")) > 2_000_000:
        raise ValueError("weather document exceeds 2 MB")
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("DTD and entities are not permitted")
    root = ET.fromstring(xml)
    issued = root.findtext("./amoc/issue-time-utc")
    if not issued:
        raise ValueError("missing BoM issue-time-utc")
    timestamp(issued)
    area = next((a for a in root.findall("./forecast/area") if a.get("aac") == area_aac), None)
    if area is None:
        raise ValueError("requested BoM area code absent")
    periods = []
    for period in area.findall("forecast-period"):
        start = period.get("start-time-utc")
        end = period.get("end-time-utc")
        if not start or not end or timestamp(end) <= timestamp(start):
            raise ValueError("invalid BoM forecast period")
        values = {e.get("type"): "".join(e.itertext()).strip()
                  for e in period if e.tag in ("text", "element") and e.get("type")}
        periods.append({"start": start, "end": end, "values": values})
    if not periods:
        raise ValueError("no forecast periods in selected area")
    return {"provider": "Bureau of Meteorology", "issued_at": issued,
            "area_aac": area_aac, "periods": periods,
            "role": "weather_context_only", "commercial_rights": "not_assumed"}


def weather_is_fresh(context: dict, now: datetime, max_hours: float = 12) -> bool:
    if now.utcoffset() is None or not 0 < max_hours <= 48:
        raise ValueError("use an aware time and a bounded freshness window")
    age = (now - timestamp(context["issued_at"])).total_seconds() / 3600
    active = any(timestamp(p["start"]) <= now < timestamp(p["end"]) for p in context["periods"])
    return 0 <= age <= max_hours and active
