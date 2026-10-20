# EPIC-037E — The fake exchange is demanding by default: faults, reorderings and invariants

**Status:** 🟡 In progress — first slice delivered 2026-10-20 (the exchange's refusals); the rest moved to [EPIC-037G](EPIC-037G_seeded_faults_and_invariants.md)
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🔴 — slower and potentially flaky integration tests; a new test dependency
**Complexity:** L — a fault plan in the fake, seeds in CI and nightly, stateful invariant tests
**Epic:** [EPIC-037](../README.md)
**Depends on:** EPIC-037D (the parity families become the first fault scenarios), for the part now in 037G

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
**Slice 1, 2026-10-20 — the fake refuses what the real exchange refuses.** The owner's coordinator re-cut the task around what had hurt (BUG-147/CS-007, BUG-221, BUG-216, BUG-231); the seeded `FaultPlan`, the invariants runner and the nightly job (criteria 1–5 above) are 037G. Decisions: [`DECISION_2026-10-20_the_fake_refuses_by_default.md`](DECISION_2026-10-20_the_fake_refuses_by_default.md).

| Refusal | Code | Default | Source | Test |
| :--- | :--- | :--- | :--- | :--- |
| Price off the tick; quantity off the step, past the maximum, zero; precision over the symbol's | `-4014`, `-4023`, `-4005`, `-4003`, `-1111` | on | USDⓈ-M error-code page, read 2026-10-20 | `tests/unit/fake_exchange/test_fake_futures_order_filters.py` |
| Notional under the minimum (reduce-only exempt) | `-4164` | on | same page | same file |
| Price outside `minPrice`/`maxPrice` | `-4013` / `-4002` | on | same page (the app does not map them: `BUG-236`) | same file |
| Order's `positionSide` not the account's mode | `-4061` | on | same page | same file |
| Timestamp outside `recvWindow` (5 000 ms) or ahead, any signed request (Futures, Spot, `/sapi/`) | `-1021` | **on** (was per test) | `BUG-221`, PR 615 | `test_fake_rate_limit.py` |
| Past the weight limit: 429 with `-1003` and `Retry-After`, then 418 | `-1003` | opt-in (`urls.rate_limit.limit`); a 418 is held for its 120 s | general-info page for 429/418 and the error-code page's `-1003` texts; `Retry-After` observed (`BUG-216`) | `test_fake_rate_limit.py` |
Already there before this slice and left alone: reduce-only that cannot reduce (`-2022`, `-2022` on an excess), margin (`-2027`, `-2019`), `-2011` on a cancel of an unknown order, `-4067`/`-4068`, partial fills (`move_price(fill_at_most=)`), late fills (`faults.hold_fills`), duplicate reports, `reject_next_order` (any code, so `-2010`/`-2015`), a stale open-orders list.

**Stability of the `-1021` default:** `tests/integration/modules/bots`, `modules/trading` and `infrastructure` (448 tests, 4 workers) ran three times in a row on the merged tree: 448 passed each time. The 20-run check is in 037G.

**Findings the stricter fake exposed (none in product code):**
- `test_a_start_is_refused_when_the_venue_will_not_make_its_settings_the_bots` placed a 50 USDT resting order on a symbol whose minimum notional is 100: Binance refuses it with `-4164`. The order is now 100 USDT; the assertions are untouched.
- `test_order_book_state.py` placed `0.002` ETHUSDT, off the `0.01` step. Fixed the same way.
- `test_a_futures_run_that_began_a_moment_ago_is_read_whatever_the_clock_error` moves the exchange's clock between requests to stamp orders on either side of a run's start; with `-1021` on, the requests themselves fell outside the receive window. It sets `urls.clock.enforcing = False` with the reason: its subject is the history window, not the timestamp rule (which `test_a_stepped_clock_is_measured_again_on_the_first_rejected_timestamp.py` and the halt journey own).
- The translator maps none of `-4014`, `-4023`, `-4005`, `-4013`, `-4002` for Futures (reviewer round 1): `BUG-236`, filed Open, not fixed here.
- `test_workbench_conformance[True-1024x700]` fails on a clean checkout of this container too (Qt offscreen); not caused by this change.
