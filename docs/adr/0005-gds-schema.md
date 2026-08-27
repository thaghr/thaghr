# ADR 0005: Graded Degradation Score (GDS) schema, locked pre-Phase 3

**Status:** Accepted, 2026-08-01

## Context
pass^k (ADR-driven by the τ-bench definition) is binary per episode: an episode either fully succeeds or it doesn't. This is the right primary metric, but it discards information when an agent partially completes a multi-step task. thaghr needed a schema that supports both a simple pass/fail mode for users who don't want to decompose tasks, and a weighted-subtask mode for users who want partial-credit resolution.

## Decision
Two schema types in `schema.py`:
- `TaskDefinition`: a set of subtasks, each with a weight, weights summing to 1.0.
- `EpisodeResult`: stores the raw `subtask_results` dict (not a precomputed score), exposes `.gds()` to compute the weighted Graded Degradation Score and `.pass_1()` for the binary pass^k input, both derived on demand from the same raw data.
- `single_check()` fallback: users who don't want to decompose tasks get a plain pass/fail path with zero extra authoring, which internally is just a `TaskDefinition` with one subtask at weight 1.0.

## Consequences
- Every run captures enough raw detail (`subtask_results`) to compute both pass^k and GDS after the fact, without re-running anything, which matters for Phase 4's promise that GDS is reported as the primary metric when pass^k rounds to 0%.
- Users pay zero authoring cost if they don't care about partial credit (`single_check()`), so GDS doesn't become friction for the common case.
- Open question deliberately deferred past this ADR, to Phase 3-5: how users author subtask weights and register checks (Python callables vs. a config DSL), and how much GDS detail actually surfaces on the Phase 5 report card. Phase 5's own DoD says cut GDS from the card entirely if two axes make it harder to parse in under 20 seconds.
