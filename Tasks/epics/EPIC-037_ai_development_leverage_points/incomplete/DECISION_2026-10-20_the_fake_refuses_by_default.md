# ADR — The fake Futures exchange refuses what Binance refuses, on by default, with opt-outs that say why

**Epic:** [EPIC-037](../README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** agent, on the coordinator's recommendations the owner pre-approved on 2026-10-20 (ONBOARDING §7); the owner may veto any row and a veto reverts it

| Label | Meaning |
| :--- | :--- |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7 |
| ✅ Established | confirmed on the code tree |

## 1. Context
The fake let through the defects of `BUG-147` (filter skipped), `BUG-221` (`-1021`), `BUG-216` (rate limit) and `BUG-231` (`-2022`, closed as account-side). Its order route (`order_book_state.py` → `OrderBookState.place`) checked reduce-only and margin only. ✅ Established: no tick, step or notional check, no position-mode check, and `ClockPolicy.enforcing` defaulted off.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | Filters (tick, step, size, precision, notional) and `-4061` are on by default, with no switch | Accepted | 🤖 Agent decision | A test whose order Binance would refuse fails; three tests were found that relied on the leniency and fixed in their setup, none in product code |
| D2 | `-1021` is on by default; a test that moves the exchange's clock to stamp history opts out with a stated reason | Accepted | 🤖 Agent decision | The two skew-and-history tests needed the opt-out; the preflight and halt journeys already passed |
| D3 | The 429/418 policy is opt-in (`urls.rate_limit.limit`) | Accepted | 🤖 Agent decision | Journeys that never reach 2 400 weight stay as they were; a test states the limit it wants |
| D4 | The filters are read from the same table `exchangeInfo` serves (`futures_listing.py`) | Accepted | 🤖 Agent decision | What the fake advertises it enforces (`CS-007`'s lesson); a guard test walks every listed symbol |
| D5 | A price outside `minPrice`/`maxPrice` answers `-1013 Filter failure: PRICE_FILTER`; `Retry-After` is sent on 429/418 | Accepted | 🤖 Agent decision | Neither is on Binance's pages; both are the shapes the app's translator and `BUG-216`'s log use. Marked so in the module docstrings |
| D6 | `PERCENT_PRICE`, algo-order filters, Spot filters, Hedge-mode positions and the seeded fault plan are not in this slice | Accepted | 🤖 Agent decision | Moved to [EPIC-037G](EPIC-037G_seeded_faults_and_invariants.md); the percent band needs the Futures parser to read it first |
| D7 | `hypothesis` is not added | Accepted | 🤖 Agent decision | Needs the owner's approval (`commit-rule.md` §3); nothing in this slice needs it |

## 3. Alternatives considered
- Every refusal opt-in per test: rejected, the defects above were all in tests that never asked.
- Filters from a second, hand-copied table in the order checks: rejected, a copy drifts (P3).

## 4. Open questions
None.

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D5 | [EPIC-037E](EPIC-037E_demanding_fake_exchange.md) slice 1 | In progress | `tests/unit/fake_exchange/test_fake_futures_order_filters.py`, `test_fake_rate_limit.py`; mutation-checked (tick, step, notional boundary, reduce-only exemption, position side each turn a test red) |
| D6, D7 | [EPIC-037G](EPIC-037G_seeded_faults_and_invariants.md) | Not started | Not yet verified |
