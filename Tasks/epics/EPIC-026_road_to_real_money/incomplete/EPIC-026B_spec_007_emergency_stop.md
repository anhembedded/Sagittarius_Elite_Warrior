# EPIC-026B — `SPEC-007`, Emergency Stop, is written and proven

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.4; the user (2026-09-20): *"chi nhỏ task"*.
**Risk:** 🟢 — documentation; the one code change allowed is a missing test.
**Complexity:** S — the handler, its three-step result and its tests exist (`EPIC-021K` §2.2).
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** `SPEC-007` — reserved 🔵 in [`Docs/SPEC/README.md`](../../../../Docs/SPEC/README.md)
**Depends on:** None

---

## 1. Context and problem

`EmergencyStopCommandHandler` (`src/modules/trading/application/session/emergency_stop/handler.py`)
disables, cancels every open order, closes every position with a `LIVE` client, and answers with
`EmergencyStopResult` carrying one `EmergencyStopStepResult` per step. `SPEC-004` §6 already
describes it in one paragraph and calls it "planned". This epic later gives the same command a
second trigger — the circuit breaker (`EPIC-026L`, ADR D9) — and stage 3 changes its venue gate.
Both need the specified, proven flow to exist first.

## 2. Acceptance criteria

- [ ] `Docs/SPEC/SPEC-007_stop_everything_at_once.md` exists from the template and is ✅ in the
      index's main table.
- [ ] §3 lists the three steps **in the handler's order** and states that each is attempted even
      if the previous one failed, if that is what the code does — verified by reading, and by
      `tests/unit/modules/trading/application/session/test_emergency_stop.py`.
- [ ] §5 has one row per partial outcome (disable ok / cancel failed / close ok, and so on) and
      states that a partial stop is reported as three separate results, never collapsed to a
      boolean.
- [ ] §6 states what it does not promise: it does not wait for the closing orders to fill; the
      user data stream reports the fills; it does not release a strategy's symbol lease
      (`SPEC-004` §6's reasoning).
- [ ] §4 states the invariant from `BUG-088`: an Emergency Stop that lands during an enable wins.
- [ ] §8 cites existing tests plus the **the user runs it** row that `EPIC-021K` §5 already
      defined (press Emergency Stop, then `exchange-status` shows zero open positions).

## 3. Design

As `EPIC-026A`: written from the handler and its tests. The docstring at the top of the handler
explains why the steps bypass `ExecuteOrderCommand` and `DisableTradingCommand`; §7 of the SPEC
records that as the ports it *does not* cross, because that is the fact a future reader will
otherwise "fix".

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `Docs/SPEC/SPEC-007_stop_everything_at_once.md` | New |
| `Docs/SPEC/README.md` | `SPEC-007` moves to the main table as ✅ |
| `Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md` | §6's "(SPEC-007, planned)" becomes a link |
| `tests/unit/modules/trading/application/session/test_emergency_stop.py` | Only if a §5 row is uncovered |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Index consistent, paths exist | `.venv/bin/python -m pytest tests/unit/architecture/test_spec_index_is_consistent.py -q` | unit (guard) | green |
| Partial outcomes covered | `.venv/bin/python -m pytest tests/unit/modules/trading/application/session/test_emergency_stop.py -q` | unit | green |
| Human row | the user presses Emergency Stop with one open Testnet position; three ✔/✘ lines; `exchange-status` shows 0 positions | human | recorded here |
| Documentation guards | `python3 scripts/check_skill_prompt_references.py` | doc | clean |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
