# EPIC-034D — Connect: one account snapshot per venue gates the chart and the plan

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — a new port read by the whole Bots mode
**Complexity:** M — a port, a snapshot value object, a failure kind, the identity strip
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034A](EPIC-034A_bots_mode_says_what_it_knows.md)

---

## 1. Context and problem
Decision D1: a bot's first step is Connect. Today the chart and the plan open whether or not the account can be read, and a Spot Testnet maintenance page reaches the log as an "unclassified exception" (the owner's `-TestnetOnly` run, 2026-10-07: `APIError(code=0): Invalid JSON error message from Binance: <html>`).

## 2. Acceptance criteria
- [ ] Selecting a bot reads its venue's account once (balances, commission, the key's permission to trade, the symbol's filters and price) into an immutable `VenueAccountSnapshot` with its read time; bots on the same venue share it; it is re-read on a timer and on Refresh (D6).
- [ ] Until the snapshot succeeds, the chart and the Plan are disabled and say why in the user's words: no key, key rejected (`KEY_REJECTED`), exchange under maintenance (a new `MAINTENANCE` kind for an HTML answer), network; with Retry.
- [ ] An identity strip above the bot shows its name, kind, venue title with the Connect result and the available balances, and its saved state; the status bar shows the selected bot's venue.
- [ ] Reading never needs trading and never places anything.

## 3. Design
An application port `IVenueAccountReader` returning a `VenueAccountSnapshot` or a `ConnectFailure`; the Binance adapter reuses the readers that exist. The step state starts the readiness FSM that `EPIC-034H` completes; this task adds only the Connect states, in a `*_fsm_matrix.py`. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/` | the port and the snapshot |
| `src/modules/trading/adapters/binance/` | the adapter, the `MAINTENANCE` classification |
| `src/modules/bots/ui/bots_screen/` | identity strip, gating |

## 5. Testing
Unit: the classification of an HTML answer, red first; the gate on the real presenter. Integration on the composed app with the fake Binance server. A reviewer is required. Not run.

## Implementation notes (written when done)
Not started.
