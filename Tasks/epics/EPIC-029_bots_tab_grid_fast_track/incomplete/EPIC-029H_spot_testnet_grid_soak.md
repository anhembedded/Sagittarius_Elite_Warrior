# EPIC-029H — One Grid bot trades on Spot Testnet across restarts and an Emergency Stop, and its record matches the backtest of the same period

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md). This is the fast track's goal: *"để nhanh
chóng giao dịch thật"*, trading for real, which means on Spot Testnet (the user, 2026-10-03).
**Risk:** 🟡 — Testnet liquidity and price paths differ from mainnet. The soak proves mechanics,
not profitability.
**Complexity:** M — a gated Testnet test, a soak procedure the user runs, and a written report.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029E`, `EPIC-029F` and `EPIC-029G`. `EPIC-029D` is needed for the comparison.

---

## 1. Context and problem

The fake exchange proves the logic. Only a real exchange API proves these:

- acceptance;
- partial fills;
- the cancel payload (ADR D8);
- the order rate;
- behaviour across a restart.

`EPIC-028N` established the tier: `tests/testnet/`, gated by `SEW_TESTNET_TESTS=1`, run by the
user with their own keys.

## 2. Acceptance criteria

- [ ] **Gated Testnet test.** `tests/testnet/test_grid_bot_round_trip.py` runs a narrow grid (4
  levels, around the last price, at the minimum notional). It asserts:
  - every level is RESTING on the exchange, with the bot's tag;
  - a cancel from outside is re-placed;
  - Stop cancels everything and leaves no tagged open order.
- [ ] **Soak.** The user runs one Grid bot for at least 24 hours on Spot Testnet, with at least
  two app restarts and one Emergency Stop followed by a confirmed re-plan.
- [ ] **Soak report.** `Tasks/reports/` records:
  - the cycles completed;
  - the realised grid profit against the fills on the exchange's trade history;
  - every HALTED or ERROR, with its cause;
  - the open orders after each restart, against the saved levels.
- [ ] **Backtest comparison.** `EPIC-029D` replayed on the soak period, with the same parameters,
  is set beside the live record. Any difference in cycles is explained by the fill rule or by
  Testnet liquidity. It is never left unexplained.

## 3. Design

- **Same shape as `EPIC-028N`.** The procedure mirrors it: the user sets the Testnet keys
  (never pasted into chat), runs the gated test, then starts the soak from the Bots tab. The
  agent reads the log files the user returns.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `tests/testnet/test_grid_bot_round_trip.py` (new) | gated round trip |
| `Tasks/reports/grid_soak_<date>.md` (new) | soak report |

## 5. Testing

- **The Testnet tier itself, run by the user.** The agent verifies from the log: every expected
  test passed (not skipped), and there was no `Traceback`.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
