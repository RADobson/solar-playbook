# Optional AI providers

## Small local host, remote inference

A Raspberry Pi sends a short HTTPS request to a selected provider and receives structured advice. The model runs at that provider. No local GPU, Mac mini or Ollama installation is needed. The deterministic planner remains local and continues when AI is disabled, offline, rate-limited or over its allowance.

The current adapter explains a simulated plan and may suggest one of three named modes. It **does not apply** that suggestion. A later strategy layer may use approved suggestions as candidate inputs, but every result must still pass deterministic feasibility checks and owner policy. Do not ask an LLM to calculate the electrical balances or invent missing weather observations.

## Provider contract

| Config value | API format | Notes |
|---|---|---|
| `none` | No request | Default; zero AI cost |
| `openai` | Responses API, JSON schema | Fixed official endpoint; `store: false`; configured model |
| `anthropic` | Messages API, structured tool-shaped response | Tool envelope is parsed as advice; nothing is executed |
| `openai_compatible` | Chat Completions with JSON mode | Explicit HTTPS base URL; provider/model must support this request shape |
| CLI `--ollama` | Local Ollama chat | Optional existing local installation; separate from cloud config |

An OpenAI-compatible API is an interface claim, not a promise that every parameter/model behaves identically. Test the selected model for JSON mode, token limits, latency, refusals and incomplete output. DeepSeek currently documents compatible endpoints and is one candidate; other providers can fit the same boundary after validation. [DeepSeek API](https://api-docs.deepseek.com/).

Use the provider's current model identifier and pricing when configuring it. The repository deliberately does not silently select “the latest cheapest” model. Model changes should go through the same fixture-based evaluation as code changes.

## Configuration

Copy `examples/ai-config.json` into `private/ai-config.json`. It ships with AI disabled. Choose `provider`, set `enabled` to true, specify the current model, and place the key in the environment variable named by `api_key_env`. Never put the actual key in this JSON or a Git commit.

For OpenAI or Anthropic, leave `base_url` empty. For a compatible provider, specify the API prefix before `/chat/completions`; for example DeepSeek's documented `https://api.deepseek.com` prefix. This is an explicit choice of recipient for the request. There is no automatic switch to another provider after an outage.

```sh
python3 -m solar_playbook demo \
  --ai-config private/ai-config.json \
  --ai-ledger private/ai-allowance.sqlite3 \
  --out out/explained
```

The key must already be set privately in the process environment. Consumer ChatGPT/Claude subscriptions should not be assumed to include API credits; establish the provider API account and billing terms separately. No API account or paid request was created by this project build.

## Cost controls that exist now

The client sends at most one request per CLI invocation. The persistent SQLite ledger atomically enforces a configured daily call count (default four) and a monthly **request reservation allowance** in USD. It reserves the configured amount before calling the provider and does not release it after failed/ambiguous responses. There are no automatic retries. All processes for a household must share the same persistent ledger.

The default US$2 monthly allowance and US$0.05 reservation per request are illustrative operator settings, **not quoted prices**. A reservation ledger cannot guarantee the provider's actual invoice: rates, token accounting, reasoning usage and other clients can differ. Set a suitable provider-side hard spending limit where available, use a dedicated project/key, and reconcile actual usage. Never describe a budget alert as a hard provider limit.

Output is capped at 512 tokens in the request; the input is a small bounded summary. Responses over 100 KB, invalid JSON, refusals, incomplete responses, timeout and allowance exhaustion all produce a local fallback. Schema validity does not establish factual quality.

Cost estimation should be explicit:

```text
monthly API cost = requests_per_month *
  (average_input_tokens * input_price_per_million
   + average_output_tokens * output_price_per_million) / 1,000,000
```

Add any billed reasoning/cache/tool charges and applicable currency conversion/taxes. As pure arithmetic, four calls/day for 30 days at 2,000 input and 300 output tokens consume 240,000 input and 36,000 output tokens. Insert actual vendor prices; do not substitute a subscription price or assume a permanently free tier.

## Privacy and trust

v0.1 sends only the chosen strategy, simulated energy cost, added EV energy and ending battery energy. It sends no address, VIN, HA token, API key in a prompt, raw time series or free-text weather report. The API key is used only in its authentication header. Redirects are refused so credentials are not forwarded to a different endpoint.

If live household summaries are added later, obtain owner agreement for the specific provider, data and retention terms. An endpoint's country/hosting arrangements are a commercial/privacy choice, separate from model quality. `store: false` is not a universal zero-retention guarantee. Keep core automation working when cloud transmission is disabled.

## Evaluation before selecting a default

Use the same sunny/cloudy/away/invalid-input test set across providers. Score JSON compliance, numerical faithfulness, refusal/failure behaviour, median and tail latency, input/output tokens and owner usefulness. Compare the result to a deterministic template explanation. Prefer the inexpensive model that passes the evaluation; a more expensive model is optional for troubleshooting, not every telemetry update.

Official API references: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [Claude Messages](https://platform.claude.com/docs/en/api/messages/create), [compatible Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/). This release has mocked contract tests, not live provider certification.
