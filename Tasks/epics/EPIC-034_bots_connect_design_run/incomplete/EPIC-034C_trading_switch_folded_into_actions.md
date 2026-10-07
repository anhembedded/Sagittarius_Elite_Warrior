# EPIC-034C — The trading switch leaves; Start, arm and a manual order reconcile and open the order session themselves

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🔴 — moves the one guard every order passes through
**Complexity:** L — the session state, three entry points, the banner, SPEC-004
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-004](../../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md), [SPEC-005](../../../../Docs/SPEC/SPEC-005_place_a_manual_order.md), [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034B](../completed/EPIC-034B_every_venue_with_a_key_is_on.md)

---

## 1. Context and problem
`EnableTradingCommandHandler` (`src/modules/trading/application/session/enable_trading/handler.py`) is the one place the trading session is enabled. It reads the whole account every time, refuses when a position the app did not open exists, and opens the order session and the user data stream. The owner judged the switch a redundant step and chose to keep its checks inside the actions that need them (decision D3, option A).

## 2. Acceptance criteria
- [ ] No Enable/Disable trading command, toolbar button, "Trading is OFF" title or banner state remains.
- [ ] Starting a bot, arming a strategy and placing a manual order each run the same reconciliation before their first order; a position the app did not open refuses the action with the existing words, before anything is sent.
- [ ] The order session and user data stream open on the first such action for a venue and stay open; Emergency stop still cancels and closes everything and leaves the venue unable to submit until the next deliberate action.
- [ ] An architecture guard proves every order path passes the reconciliation, the successor of today's single `enable()` call-site rule.
- [ ] SPEC-004 becomes a precondition of SPEC-005 and SPEC-014, or is retired with a note; its "Proven by" tests move with it.

## 3. Design
Keep `TradingSessionState` and its generation fencing; replace the user-facing switch with one application service, `ensure_session_ready(venue)`, that the three use cases call first. The reconciliation code moves; it is not rewritten. D3's mainnet confirmation waits for `EPIC-026` to add a mainnet venue; this task leaves the hook for it. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/session/*` | the switch becomes a precondition service |
| the bot start, strategy arm and `execute_order` handlers | call the service first |
| trading UI, title, banner | the switch removed |
| `Docs/SPEC/SPEC-004*`, `SPEC-005*`, `SPEC-014*` | updated |
| `tests/unit/architecture/` | the reconciliation guard |

## 5. Testing
Unit: each entry point refuses on a foreign position, red first by deleting the call. Integration: a bot starts with no prior switch. Testnet tier: the order lifecycle runs without an enable step. A reviewer is required (feature, 🔴). Not run.

## Implementation notes (written when done)
Not started.
