# Architecture Decision Records

Lightweight ADRs for thaghr. One file per decision that would otherwise get re-litigated. Format: Status, Context, Decision, Consequences.

| # | Decision |
|---|---|
| [0001](0001-src-layout.md) | src/ layout, not flat |
| [0002](0002-provider-level-interception.md) | Provider-level interception (httpx transport), not framework-level |
| [0003](0003-apache-2-license.md) | Apache 2.0 license, not MIT or AGPL |
| [0004](0004-sqlite-default-store.md) | sqlite default store, Postgres reserved for the hosted product |
| [0005](0005-gds-schema.md) | GDS schema: TaskDefinition + EpisodeResult, locked pre-Phase 3 |
| [0006](0006-repeat-counter-not-mop-for-live-alerting.md) | Repeat-counter safeguard for live alerting; MOP stays offline |

New ADR: copy the format above, number sequentially, land it in the same commit as the decision it documents.
