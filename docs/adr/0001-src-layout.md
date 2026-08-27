# ADR 0001: Use src/ layout, not flat

**Status:** Accepted, 2026-07 (Phase 0)

## Context
Python package layout choice at repo init, before any code existed. Two options: flat layout (`thaghr/` package at repo root, alongside `tests/`) or `src/` layout (`src/thaghr/`).

## Decision
Use `src/` layout: package lives at `src/thaghr/`.

## Consequences
- Forces `pip install -e .` for local development; the package cannot be imported by accident from the repo root without installing it, which catches packaging bugs (missing `__init__.py`, bad `pyproject.toml` includes) before they reach PyPI.
- Slightly more path noise in imports and tooling config (pytest, coverage) needs `src/` awareness.
- Matches the layout used by most mature PyPI packages, reducing friction for contributors and for `pip install thaghr` correctness (Phase 8 DoD).
