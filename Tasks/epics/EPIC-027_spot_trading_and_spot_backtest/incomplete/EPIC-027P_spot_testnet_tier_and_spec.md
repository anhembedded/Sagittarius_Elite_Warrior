# EPIC-027P — A real Spot Testnet round trip is proven, and the Spot order lifecycle is a written SPEC

**Status:** 🔵 Backlog
**Source:** follows the user's *"giao dịch spot"* request, 2026-09-26; `testing-rule.md` §1 (`tests/testnet/`).
**Risk:** 🟡 — touches a real exchange (testnet); must never make someone else's CI red.
**Complexity:** M — an opt-in tier, a SPEC, the user's own confirmation run.
**Epic (optional):** [EPIC-027](../README.md)
**SPEC (optional):** a new `Docs/SPEC/` use case for the Spot order lifecycle
**Depends on:** [EPIC-027K](EPIC-027K_spot_trading_client_and_order_path.md) through [EPIC-027O](EPIC-027O_live_ui_for_spot.md)

---

## 1. Context and problem
- `tests/testnet/` is opt-in twice: `SEW_TESTNET_TESTS=1` plus Futures Testnet credentials
  (`tests/testnet/conftest.py:1-54`). `test_order_lifecycle.py:76-166` proves a Futures round trip
  and closes with `reduce_only=True`.
- No Spot tier exists, and no SPEC describes a Spot order.

## 2. Acceptance criteria
- [ ] `tests/testnet/spot/` runs only with its own opt-in flag and Spot Testnet keys. Without them it
      skips with a stated reason and never fails the gate.
- [ ] It proves a round trip: BUY a small MARKET quantity → holding appears (from the stream) → SELL it
      back → holding returns to baseline. It asserts invariants (`FILLED`, back to baseline), never
      prices, and cleans up in `finally`.
- [ ] A SPEC describes the Spot order lifecycle, with the tests that prove it listed under
      "Proven by".
- [ ] The user runs the tier once and the output is pasted into this task file.

## 3. Design
- Mirror the Futures tier's structure and its opt-in gate. Keep separate credentials (ADR D8).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/testnet/spot/conftest.py`, `tests/testnet/spot/test_spot_order_lifecycle.py` | new tier |
| `Docs/SPEC/SPEC-0nn_spot_order_lifecycle.md` + `Docs/SPEC/README.md` | new use case |

## 5. Testing
- The tier itself; the SPEC index guard (`tests/unit/architecture/test_spec_index_is_consistent.py`).
- Not run yet (needs Spot Testnet keys from the user).
