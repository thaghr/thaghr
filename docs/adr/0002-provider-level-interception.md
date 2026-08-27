# ADR 0002: Provider-level interception, not framework-level

**Status:** Accepted, pre-Phase 2

## Context
thaghr needs to inject faults (errors, latency, malformed responses) into an agent's calls to LLM providers. Two strategies were available: hook into agent frameworks (LangChain, LlamaIndex, CrewAI, etc.) at the framework layer, or intercept at the HTTP transport layer between the SDK and the provider.

Framework-level hooks are more contextual (can see tool calls, chain steps) but require a separate adapter per framework, and frameworks change their internals frequently.

## Decision
Intercept at the HTTP transport layer, using httpx's `BaseTransport` interface. This is provider-level and framework-agnostic: it works underneath any SDK (OpenAI, Anthropic, etc.) that uses httpx, regardless of what agent framework sits on top.

Framework-specific adapters, if ever needed, are deferred to Phase 5+ and layered on top of this, not built instead of it.

## Consequences
- One interception mechanism covers every framework built on the OpenAI/Anthropic Python SDKs, which is most of the ecosystem, without per-framework maintenance burden.
- Cannot fault-inject calls that bypass httpx entirely (rare, but e.g. some gRPC-based providers).
- Phase 6 proved this generalizes beyond Python too: a Node script using the OpenAI JS SDK gets faults injected via `baseURL` pointed at `thaghr proxy`, with the same transport-level design applying in proxy form.
- Determinism (record/replay) had to be built at this same layer; this turned out harder than planned and required an unplanned `cassette.py` component (see Banked Gotchas in the master skill).
