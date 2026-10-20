# EPIC-037G — Seeded faults and invariants on the fake exchange

**Status:** 🔵 Planned — not started
**Source:** the rest of [EPIC-037E](EPIC-037E_demanding_fake_exchange.md), split out on 2026-10-20 when its first slice (the exchange's refusals) shipped
**Risk:** 🔴 — slower and potentially flaky integration tests; a possible new test dependency
**Complexity:** L — seeds in CI and nightly, stateful invariant tests
**Epic:** [EPIC-037](../README.md)
**Depends on:** EPIC-037D (the parity families become the first fault scenarios)

---

## 1. Context and problem
The fake now refuses what Binance refuses (037E, slice 1). It still never *misbehaves in time*: a placement response and its stream report always arrive in one order, the user stream never drops, and nothing checks invariants after each step. BUG-194 and BUG-195 passed CI for that reason.

## 2. Acceptance criteria
Criteria 1–5 of [EPIC-037E](EPIC-037E_demanding_fake_exchange.md) §2 stand unchanged (seeded `FaultPlan`, faults on by default in the bots and trading integration folders, invariants after every step, BUG-194/195 reproduced from a seed, `hypothesis` decision). Added, from slice 1's findings:
- [ ] Filters the fake does not yet enforce: `PERCENT_PRICE` (advertise it in `futures_listing.py` and read it in `futures_metadata_parser.py`, closing the open item of `CS-007`), and the tick/step/notional of conditional (algo) orders.
- [ ] The Spot fake's `place_order` enforces the same filters from its own `exchangeInfo`.
- [ ] Hedge-mode semantics: positions per `positionSide`, and `-1106` for `reduceOnly` in Hedge mode (slice 1 only refuses a mismatch with `-4061`).
- [ ] Rate-limit refusals (`urls.rate_limit`) used in one composed-app journey, so the app's pause (`BUG-216`) is proved against a 429/418 it did not script.
