"""Optional local explanation. Model output cannot become a hardware command."""
import json
from urllib.request import Request, urlopen

MODES = ("balanced", "solar_first", "tariff_first")
SCHEMA = {"type": "object", "properties": {
    "suggested_mode": {"type": "string", "enum": list(MODES)},
    "explanation": {"type": "string", "maxLength": 1200}},
    "required": ["suggested_mode", "explanation"], "additionalProperties": False}


def validate_advice(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {"suggested_mode", "explanation"}:
        raise ValueError("invalid advisor fields")
    if value["suggested_mode"] not in MODES:
        raise ValueError("invalid advisor mode")
    if not isinstance(value["explanation"], str) or not 1 <= len(value["explanation"]) <= 1200:
        raise ValueError("invalid advisor explanation")
    return value


def advise(report: dict, model: str = "qwen3:4b") -> dict:
    selected = report.get("selected")
    if not selected:
        return {"source": "fallback", "suggested_mode": "balanced",
                "explanation": "No feasible plan. Retain native control and review the input."}
    # Numeric summary only; never submit VINs, tokens or arbitrary weather prose.
    summary = {key: selected[key] for key in
               ("strategy", "energy_cost_aud", "ev_added_kwh", "ending_battery_kwh")}
    payload = {"model": model, "stream": False, "format": SCHEMA,
               "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 500},
               "messages": [
                   {"role": "system", "content": "Explain this simulated home energy plan briefly. "
                    "Suggest only an allowed mode. Do not claim real savings, weather certainty, "
                    "or issue instructions to equipment. Values are AUD and kWh."},
                   {"role": "user", "content": json.dumps(summary)}]}
    try:
        request = Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=20) as response:
            raw = response.read(100_001)
        if len(raw) > 100_000:
            raise ValueError("oversized model response")
        advice = validate_advice(json.loads(json.loads(raw)["message"]["content"]))
        return {"source": "ollama", **advice}
    except (OSError, ValueError, KeyError, TypeError):
        return {"source": "fallback", "suggested_mode": "balanced",
                "explanation": "Local model unavailable or invalid. The deterministic plan remains unchanged."}
