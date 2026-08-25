# EPIC-009A — Retire the legacy Sanity tier, rebuild it as composition-root scans

**Status:** ✅ Done — 2026-08-25
**Depends on:** nothing (first piece)

## What

Replaced 7 of 9 `tests/sanity/` modules (moved to
`Tasks/reference/sanity_legacy/` for test-case reference, outside any
collected path) and the empty `tests/integration/test_ui_sanity.py` with:

- `tests/sanity/conftest.py` — one session-scoped `booted_app` fixture
  (was 6 drifted copies, one function-scoped boot per test), and
  `diagnostic_guard` — autouse, fails on any Qt message / Python log
  record / `warnings.warn(...)` during boot-construct-shutdown.
- `tests/sanity/test_composition_root.py` — scans, never lists: every
  use case resolves (replacing 2 hand-written allowlists), every
  strategy on disk is registered, every navigable route constructs,
  every screen package has a route, shutdown completes within budget.

Kept as-is (already scan-based, already had a drift guard):
`test_circular_imports.py`, `test_view_model_thread_affinity_sanity.py`.

## Proof

Run against a real Python 3.12.3 environment with the engine installed
(not assumed): 1 app boot instead of ~24, tier runtime ~4s instead of the
old tier's multi-minute sequential run. All 4 navigable routes construct
under `offscreen` with the *full* production bootstrap — the old tier
never exercised 2 of 4 screens at all (`BUG-019`'s class of gap).

## Findings this piece produced

- `BUG-044` (P1, closed) — published engine had Python-2 `except` syntax.
- `BUG-045` (P2, closed by `EPIC-009B`) — sanity reached the real network.
- Confirmed the Python floor must be 3.12 (engine's own PEP 695 syntax),
  not the previously-undeclared floor — `pyproject.toml` now declares
  `requires-python = ">=3.12"`, enforced by
  `tests/sanity/test_python_floor.py`.

## Reference

ADR `../DECISION_2026-08-25_sanity_model_and_execution.md`, D1/D3/D4/D5,
constraints C1-C4.
