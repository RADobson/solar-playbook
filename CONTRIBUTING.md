# Contributing

Run `python3 -m unittest discover -s tests -v` and a demo before submitting changes. Keep the core portable and runnable without third-party dependencies unless a demonstrated requirement justifies adding one.

Include a reproducible input fixture for scheduling bugs. Use invented or deliberately anonymised data; exclude VINs, device keys, addresses, household routines and API tokens. All examples must state their units and time zone.

Provider adapters must fail safely on incomplete responses, validate schema and units, respect quotas and preserve the planner when unavailable. Do not put control authority in an LLM prompt. Add tests for disabled mode, timeout, refusal, unexpected response and credential destination.

Hardware-write code requires documented entity/register mapping, limits, stale-data behaviour, ownership, feedback, rollback and a recorded commissioning test. Passing mocked tests alone does not make hardware compatibility verified. Preserve a read-only default.

Upstream changes should cite exact revisions and licences. Do not relabel personal-use source as unrestricted open source. Source pinning is not a security audit or proof that all pinned projects work together.

Feature requests should explain the household outcome and compare a simple native-equipment solution first. This project welcomes reuse of mature upstream components.
