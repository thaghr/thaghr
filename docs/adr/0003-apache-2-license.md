# ADR 0003: Apache 2.0 license, not MIT or AGPL

**Status:** Accepted, Phase 0

## Context
thaghr is open-source and solo-built now, with an explicit plan to raise and hire later (Phase 11). License choice affects both community adoption and enterprise self-hosting.

MIT is simpler but carries no explicit patent grant. AGPL forces network-use copyleft, which is attractive for some open-core plays but is a known adoption blocker for enterprises with legal review processes, since many enterprise legal teams blanket-ban AGPL dependencies.

## Decision
Apache 2.0.

## Consequences
- The explicit patent grant matters for enterprise self-hosters evaluating the tool, and removes a category of legal objection that MIT doesn't address.
- Unlike AGPL, does not force competitors offering thaghr as a hosted service to open-source their modifications; this is a conscious tradeoff of copyleft leverage for adoption breadth, consistent with the fundable-startup goal over pure community-protection goal.
- Compatible with the C-corp transfer planned once a co-founder signs (see ADR 0004 GitHub org decision).
