# EPIC-009F — Ratify the 12-mode failure catalogue (ADR §4, Q1)

**Status:** ✅ Done — 2026-08-25 (reviewer replied "12")
**Depends on:** nothing (should have come first; recorded honestly as
overtaken by events — `EPIC-009A/B/C` were built against the catalogue's
current *draft* form before this ratification happened)

## What

The ADR's §4 failure-mode table (12 entries: missing node, orphan node,
broken edge, wrong node, in-source-not-in-graph, in-graph-not-in-source,
cannot enter, enters degraded, cannot exit, exits dirty, entry point
uncomstructible, entry point unregistered) is still marked 🟠 Draft — not
ratified. `EPIC-009A/B/C` cover modes 1, 3, 4, 5, 7, 8, 9, 10, 11, 12 in
practice already; this task is about making that coverage a *deliberate,
agreed* design rather than one this session picked on its own read of an
unratified draft.

## Specific open calls from the ADR, still unresolved

- **Mode 2** (orphan node — registered, nothing depends on it): is this
  worth a test at all? No bug has ever exercised it; no strong argument
  for keeping it was ever made.
- **Mode 6** (in graph, not in source — a registration pointing at
  deleted code): blocked on Q2 — can `StdLibContainer` enumerate its own
  registrations? Not yet checked against the real engine API.
- **Mode 12** premise: does this project ever *intentionally* ship a
  screen package with no route (e.g. a work-in-progress screen)? If so,
  `test_every_screen_package_has_a_navigable_route` (already shipped in
  `EPIC-009A`) needs an explicit, justified skip mechanism — currently it
  has none.

## Why this matters even though work already shipped

Everything built so far is defensible against the draft as it stands and
is independently verified (real runs, fault injection, not just design
argument) — but "the design was never formally agreed" is exactly the
kind of gap `EPIC-009`'s own Principle 8 (a contract nobody executes does
not exist) warns about. Closing this task turns the ADR's status from
🔵 Proposed to something the project can point at as settled.


## Decision, as recorded in the ADR §4

- **Mode 2 (orphan node) — dropped.** No bug behind it; this codebase
  registers extension points for decided-but-unbuilt work on purpose
  (`BaseFeed`), so a test asserting "everything registered must be used"
  would false-positive on that legitimate pattern.
- **Mode 6 (registration pointing at deleted code) — kept, marked
  untestable today.** Confirmed directly against `sagittarius_engine`'s
  `StdLibContainer`: no public API enumerates registrations (only
  `bind`/`singleton`/`resolve`/`scoped`/`create_scope`). Testing it would
  mean reaching into private container state, which D4 forbids. Accepted
  as a named, open gap — reopens if `IContainer` grows an enumeration
  method upstream.
- **Mode 12 (screen package with no route) — ratified as already shipped.**
  `test_every_screen_package_has_a_navigable_route` (`EPIC-009A`) already
  covers it and is green. No skip/allowlist mechanism added ahead of a
  real need for one.

ADR moved from *Proposed* to *Approved* on this decision.
