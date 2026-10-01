# EPIC-028P — An integration test proves Phase 1: two venues in one process, against one fake exchange, never touch each other

**Status:** 🟡 In progress
**Source:** the epic-level review on PR #300 (§2, should-fix), 2026-10-01: *"'Phase 1 exit met' is claimed without the required evidence … add the dual-venue fake-exchange test, or reopen the phase."* The user agreed on 2026-10-01: *"đồng ý, làm theo đề xuất của bạn"* ("agreed, do as you propose").
**Risk:** 🟢 — tests only, plus a request log on the fake exchange
**Complexity:** S — one integration test file
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028C](../completed/EPIC-028C_both_venues_running_concurrently.md)

---

## 1. Context and problem
- Phase 1's exit row (README §4) requires an integration test against a fake exchange serving both `/fapi` and `/api` in one process. No test under `tests/integration` or `tests/sanity` does that.
- The isolation proof is unit-level only (`test_venue_isolation.py`, `Mock` clients, Emergency Stop and Enable/Disable).
- A mutation pinning order and cancel to the Futures scope was caught only by single-venue tests.

## 2. Acceptance criteria
- [ ] One fake exchange serves both venues, and the test builds both venues' real adapters against it, in one process.
- [ ] Each of the following, addressed to one venue, sends requests only to that venue's API family and changes only that venue's session state; the other venue's state and requests are untouched:
  - a market order;
  - a limit order and its cancel;
  - an Emergency Stop.
- [ ] The test runs in both directions (Futures → Spot untouched, Spot → Futures untouched).
- [ ] The README's Phase 1 exit row cites this test.

## 3. Design
To be written as built.

## 4. Changes, per file
To be written as built.

## 5. Testing
- Not run.

## Implementation notes (written when done)
Not started.
