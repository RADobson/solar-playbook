"""Provider-neutral, optional cloud advice with persistent request allowances.

Only an aggregate numeric simulation summary is sent. There are no hardware
tools. No retries, automatic provider failover or background requests occur.
"""
from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from .advisor import SCHEMA, validate_advice
from .home_assistant import NoRedirect
from .model import finite


@dataclass(frozen=True)
class AIConfig:
    provider: str = "none"
    model: str = ""
    enabled: bool = False
    api_key_env: str = "SOLAR_PLAYBOOK_AI_KEY"
    base_url: str = ""
    daily_call_limit: int = 4
    monthly_allowance_usd: float = 2.0
    reserve_per_call_usd: float = 0.05

    def validate(self):
        if self.provider not in ("none", "openai", "anthropic", "openai_compatible"):
            raise ValueError("unsupported provider")
        if type(self.enabled) is not bool or type(self.daily_call_limit) is not int:
            raise ValueError("invalid enable flag or call limit")
        if not 0 <= self.daily_call_limit <= 24:
            raise ValueError("call limit must be in [0,24]")
        for key in ("monthly_allowance_usd", "reserve_per_call_usd"):
            finite(getattr(self, key), key)
        if not 0 < self.reserve_per_call_usd <= self.monthly_allowance_usd <= 100:
            raise ValueError("invalid USD request allowance")
        if not isinstance(self.model, str) or not isinstance(self.base_url, str):
            raise ValueError("model and endpoint must be strings")
        if not isinstance(self.api_key_env, str) or not self.api_key_env or not all(c.isalnum() or c == "_" for c in self.api_key_env):
            raise ValueError("invalid environment variable name")
        if self.enabled and self.provider != "none" and not self.model.strip():
            raise ValueError("select a current provider model explicitly")
        if self.provider == "openai_compatible":
            parsed = urlparse(self.base_url)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment):
                raise ValueError("compatible endpoint must be an explicit HTTPS origin/path")
        elif self.base_url:
            raise ValueError("custom base URL is only allowed for openai_compatible")


class AllowanceLedger:
    """Atomic local call reservations, not a provider billing guarantee.

    Failed/ambiguous requests retain their reservation. SQLite serialises
    competing processes; all household requests must use the same ledger.
    """
    def __init__(self, path: Path):
        self.path = path

    def reserve(self, config: AIConfig, now: datetime) -> bool:
        config.validate()
        if now.utcoffset() is None:
            raise ValueError("allowance clock must be timezone aware")
        now = now.astimezone(timezone.utc)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=2)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS requests (day TEXT, month TEXT, reserve_usd REAL)")
            db.execute("BEGIN IMMEDIATE")
            calls = db.execute("SELECT COUNT(*) FROM requests WHERE day=?", (now.strftime("%Y-%m-%d"),)).fetchone()[0]
            reserved = db.execute("SELECT COALESCE(SUM(reserve_usd),0) FROM requests WHERE month=?", (now.strftime("%Y-%m"),)).fetchone()[0]
            if calls >= config.daily_call_limit or reserved + config.reserve_per_call_usd > config.monthly_allowance_usd + 1e-9:
                return False
            db.execute("INSERT INTO requests VALUES (?,?,?)", (now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"), config.reserve_per_call_usd))
            return True


def build_request(summary: dict, config: AIConfig, key: str) -> Request:
    config.validate()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("missing or invalid API key")
    # Use the common schema subset; length is still checked locally.
    schema = json.loads(json.dumps(SCHEMA))
    schema["properties"]["explanation"].pop("maxLength", None)
    system = ("Explain the supplied simulated home-energy plan. Return a JSON object with "
              "suggested_mode (balanced, solar_first, or tariff_first) and explanation. "
              "You only advise; never claim equipment was controlled or real savings were measured. "
              "Use at most 1200 characters for the explanation. Money is AUD; energy is kWh.")
    prompt = json.dumps(summary, allow_nan=False)
    if len(prompt) > 4000:
        raise ValueError("summary exceeds request size limit")
    headers = {"Content-Type": "application/json"}
    if config.provider == "openai":
        url = "https://api.openai.com/v1/responses"
        headers["Authorization"] = "Bearer " + key
        body = {"model": config.model, "store": False, "instructions": system, "input": prompt,
                "max_output_tokens": 512, "text": {"format": {"type": "json_schema", "name": "energy_advice", "strict": True, "schema": schema}}}
    elif config.provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        body = {"model": config.model, "max_tokens": 512, "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [{"name": "summarise_plan", "description": "Return advice only; no action is executed.", "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": "summarise_plan"}}
    elif config.provider == "openai_compatible":
        url = config.base_url.rstrip("/") + "/chat/completions"
        headers["Authorization"] = "Bearer " + key
        body = {"model": config.model, "max_tokens": 512, "stream": False,
                "response_format": {"type": "json_object"},
                "messages": [{"role":"system","content":system},{"role":"user","content":prompt}]}
    else:
        raise ValueError("provider is disabled")
    return Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")


def parse_response(data: dict, provider: str) -> dict:
    if provider == "openai":
        if data.get("status") != "completed":
            raise ValueError("incomplete model response")
        texts = [part["text"] for item in data.get("output", []) if item.get("type") == "message"
                 for part in item.get("content", []) if part.get("type") == "output_text"]
        value = json.loads("".join(texts))
    elif provider == "anthropic":
        if data.get("stop_reason") != "tool_use":
            raise ValueError("incomplete structured advice")
        blocks = [item for item in data.get("content", []) if item.get("type") == "tool_use"]
        if len(blocks) != 1 or blocks[0].get("name") != "summarise_plan":
            raise ValueError("unexpected structured advice")
        value = blocks[0]["input"]
    else:
        choice = data["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("incomplete compatible response")
        value = json.loads(choice["message"]["content"])
    return validate_advice(value)


def advise_cloud(report: dict, config: AIConfig, ledger: AllowanceLedger,
                 now: datetime | None = None) -> dict:
    fallback = {"source":"fallback", "suggested_mode":"balanced",
                "explanation":"Optional cloud advice was not used; the local plan is unchanged."}
    config.validate()
    if not config.enabled or config.provider == "none" or not report.get("selected"):
        return fallback | {"reason":"disabled_or_no_plan"}
    selected = report["selected"]
    summary = {name:selected[name] for name in
               ("strategy","energy_cost_aud","ev_added_kwh","ending_battery_kwh")}
    try:
        request = build_request(summary, config, os.environ.get(config.api_key_env, ""))
        if not ledger.reserve(config, now or datetime.now(timezone.utc)):
            return fallback | {"reason":"request_allowance_reached"}
        with build_opener(NoRedirect).open(request, timeout=20) as response:
            raw = response.read(100_001)
        if len(raw) > 100_000:
            raise ValueError("oversized model response")
        advice = parse_response(json.loads(raw), config.provider)
        return {"source":config.provider, "model":config.model, **advice}
    except (OSError, ValueError, KeyError, TypeError, IndexError, sqlite3.Error):
        return fallback | {"reason":"provider_or_ledger_unavailable"}
