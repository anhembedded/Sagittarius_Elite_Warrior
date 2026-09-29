# EPIC-028N — One real round trip on each desk, in the same process, on Testnet

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — touches two real testnets at once; must never make regular CI red
**Complexity:** S — extends the existing opt-in tier
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028K](EPIC-028K_futures_desk_screen.md), [EPIC-028L](EPIC-028L_spot_desk_screen.md)

---

## 1. Context and problem
- `tests/testnet/` proves Futures and Spot round trips separately, each in a single-venue process (EPIC-027P).

## 2. Acceptance criteria
- [ ] With `SEW_TESTNET_TESTS=1` and both key pairs, one test process opens a Futures position and closes it and buys then sells Spot, through `IVenueContexts`, and both return to baseline.
- [ ] Without the flag or either key pair it skips with a stated reason.
- [ ] The user's run is pasted into this task file.

## 3. Design
Reuse the EPIC-027P fixtures; build both contexts from one config.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/testnet/test_dual_venue_round_trip.py` | new |

## 5. Testing
The user runs `ci-local.ps1 -TestnetOnly`; output pasted here.
- Not run.

## Implementation notes (written when done)
Not started.
