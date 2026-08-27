# ADR 0004: sqlite as the default store, Postgres reserved for the hosted product

**Status:** Accepted, Phase 0

## Context
Campaign runs (Phase 3) need to persist `EpisodeResult` rows somewhere. The open-source CLI tool and the future hosted product (Phase 10) have different operational contexts: the CLI runs on a stranger's laptop or CI runner with zero setup expectation, while the hosted product runs on infrastructure thaghr controls.

## Decision
sqlite is the default and only store for the open-source CLI. Postgres is reserved for the hosted product only, and is not exposed as a CLI storage backend.

## Consequences
- `pip install thaghr && thaghr run` works with zero external dependencies, no database to stand up, which directly serves the Phase 8 DoD (`pip install thaghr` works for a stranger).
- Keeps the OSS surface area small: no connection-string config, no migration story to support across arbitrary user Postgres versions.
- The hosted product's storage layer is a separate, unshared code path from the CLI's, which is intentional: it can evolve (Postgres, multi-tenant schema, etc.) without OSS compatibility constraints.
- If community demand for a shared/team sqlite alternative emerges later, that is a new decision, not a reversal of this one.
