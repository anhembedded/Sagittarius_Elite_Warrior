# EPIC-009B — OUT-of-process layer: `build()`/`teardown()` split + `--self-check`

**Status:** ✅ Done — 2026-08-25
**Depends on:** `EPIC-009A` (same `booted_app`/`diagnostic_guard` conventions)

## What

`src/presentation/ui/app_bootstrapper.py`: `main()` was one function
owning boot, UI construction, the event loop, and shutdown together —
untestable as a whole, and nothing for Sanity to launch except a bespoke
re-composition. Split into:

- `build() -> AppRuntime` — everything up to, not including, `app.exec()`.
- `teardown(runtime)` — the real shutdown path (window, watchdog, signal
  timer, engine, in that order).
- `main()` reduced to `build() -> app.exec() -> teardown() -> sys.exit()`.
- `--self-check` — D2b's degenerate control session: boot for real, one
  event-loop turn, real exit code. Not the general control channel
  (publish/dispatch from outside the process) — that stays `Proposed`,
  gated on security-relevant open questions (Q14-Q19 in the ADR).

`tests/sanity/test_self_check_process.py` — 3 tests, real
`subprocess.run(...)` launch of the real entry point. The only layer
that can prove modes 7/9/10 (cannot enter / cannot exit / exits dirty):
inside pytest, `teardown()` returning is not the same as the process
dying.

## Proof

Verified by fault injection, not just by passing green. Injected a raise
inside `teardown()` twice (before any step ran; after `app_engine.stop()`
already completed) to confirm the test detects a real failure. Both times
the process **hung** instead of exiting non-zero — not the predicted
failure mode.

## Finding this piece produced

`BUG-048` (P1, open) — `sys.excepthook`'s fallback UI calls
`dialog.exec()` unconditionally; under `QT_QPA_PLATFORM=offscreen`
nothing can dismiss it, so *any* uncaught exception after boot hangs the
real process forever. A plausible undiagnosed cause behind
`BUG-007`/`023`/`041`. Not fixed here — root cause identified, fix is a
separate piece of work.

## Reference

ADR `../DECISION_2026-08-25_sanity_model_and_execution.md`, D2/D2b, D3.
