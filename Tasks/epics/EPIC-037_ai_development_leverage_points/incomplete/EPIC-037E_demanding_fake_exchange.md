# EPIC-037E — The fake exchange is demanding by default: faults, reorderings and invariants

**Status:** 🔵 Planned — not started
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🔴 — slower and potentially flaky integration tests; a new test dependency
**Complexity:** L — a fault plan in the fake, seeds in CI and nightly, stateful invariant tests
**Epic:** [EPIC-037](../README.md)
**Depends on:** EPIC-037D (the parity families become the first fault scenarios)

---

## 1. Context and problem
Class B ("forgiving double; blind gate") is 23 of 192 reports and the owner found only 4 of them; the gate stays green while the defect is live. BUG-194 passed CI because the integration harness's pacer always delivered stream reports before the next order turn. The fake exchange is kinder than Binance (leverage point 9, delays: defects surface in real trading instead of CI).

## 2. Acceptance criteria
- [ ] A seeded `FaultPlan` on the fake exchange can inject: user-stream drop and delay; placement response and stream report in either order; partial fills; `-2010` and `-2015` refusals; clock skew.
- [ ] Faults are **on by default** in `tests/integration/modules/bots` and `trading`; each scenario runs under N seeds; a failure prints its seed; CI uses fixed seeds, a nightly job random ones.
- [ ] Invariants are checked after every step: inventory never negative; no SELL above what is held; every fill counted exactly once; every halt has a named reason.
- [ ] BUG-194's shape and BUG-195's shape (`-2010` on resume) reproduce from a seed alone.
- [ ] If the owner approves `hypothesis`, the invariants run as a `RuleBasedStateMachine`; otherwise a hand-written seeded runner is used and the choice is recorded.

## 3. Design
Fault injection in the spirit of Jepsen and stateful property testing. The fake must never be told how the code under test behaves; only the exchange's real behaviours are modelled.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/.../fake_binance_server` (current fake exchange) | `FaultPlan` and seed |
| `tests/integration/modules/bots/conftest.py`, `trading/conftest.py` | faults on by default |
| `tests/integration/modules/bots/test_grid_invariants_under_faults.py` | new stateful test |
| `.github/workflows/` | nightly random-seed job |
| `requirements*.txt` | `hypothesis`, only with the owner's approval |

## 5. Testing
Integration tier; the two reproductions red on a pre-fix commit and green on master, recorded with their seeds. Flake check: 20 consecutive runs with fixed seeds.

## Implementation notes (written when done)
Not started.
