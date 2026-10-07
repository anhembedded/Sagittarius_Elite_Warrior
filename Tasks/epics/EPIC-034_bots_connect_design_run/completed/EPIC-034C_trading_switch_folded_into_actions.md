# EPIC-034C — The trading switch leaves; Start, arm and a manual order reconcile and open the order session themselves

**Status:** ✅ Done (2026-10-07)
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
- [x] No Enable/Disable trading command, toolbar button, "Trading is OFF" title or banner state remains.
- [x] Starting a bot, arming a strategy and placing a manual order each run the same reconciliation before their first order; a position the app did not open refuses the action with the existing words, before anything is sent.
- [x] The order session and user data stream open on the first such action for a venue and stay open; Emergency stop still cancels and closes everything and leaves the venue unable to submit until the next deliberate action.
- [x] An architecture guard proves every order path passes the reconciliation, the successor of today's single `enable()` call-site rule.
- [x] SPEC-004 becomes a precondition of SPEC-005 and SPEC-014, or is retired with a note; its "Proven by" tests move with it.

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

Run (2026-10-07): unit, integration and sanity tiers on the branch; the commit tier (`ci-local.ps1 -SkipTests`: ruff, format, mypy, reference check). Two failures that also fail on `master-warrior` in this container and are not this task's: `test_workbench_conformance[True-1024x700]` (the Backtest mode needs 706 px of 700) and the sanity `test_the_window_shuts_down_within_budget` (a non-daemon pool thread the Bots presenter starts; it counts three more pool threads now that both desks are built at start, see below). **The testnet tier was not run: no credentials in this session** (`SEW_TESTNET_TESTS` and the Spot/Futures key variables are unset); its Spot round trip now opens the session through `open_session` and has no enable step.

## Implementation notes
- **The move.** `EnableTradingCommandHandler`'s body is `SessionReadiness.ensure_ready(venue)` (`application/session/session_readiness.py`), unchanged except for three things the switch did not need: an open session answers `ready` at once with nothing read (`already_open`; reconciling again would refuse on the app's own positions and `enable()` would clear every bot's budget), calls for one venue are serialised, and the result is `SessionReadyResult` / `SessionBlockReason` (renamed). `EnsureSessionReadyCommand` and its handler are the thin door behind `ITradingSession.ensure_ready()`. `DisableTradingCommand`, `ITradingSession.disable()` and `TradingSwitchCause.DISABLED` are gone.
- **The three actions.** Start bot (`GridStartPreconditions`, before the lease and the budget), Arm strategy (`ArmStrategyCommandHandler`, after the refusals that cost nothing, before the lease) and the manual order (`ExecuteOrderCommandHandler`, when `OrderRequest.opens_session`, which only the order panel sets). The refusal words are the switch's (`session_block_words.py`), reworded where they named it.
- **A late automated order never reopens a stopped session.** The task file says `execute_order` calls the service first; done literally, a bot's or a strategy's order that races an Emergency Stop would reconcile (the stop has just closed every position, so it passes) and reopen the session. So `execute_order` reconciles only for a manual live order (`opens_session`); everything else reaches `TRADING_SWITCH_OFF`, as before. `test_an_automated_order_never_reopens_a_closed_session` is red without the condition.
- **The rule that refused arming while trading was ON could not stay as it was.** With no switch the session stays open after the first action, which would have refused every arm after a Start. Restated as its cause: Arm is refused (`POSITION_OPEN`) when the app has a position open on the symbol being armed or already armed, and Disarm is refused by the same cause, only while the session is open (a closed one knows no positions). This is a decision made in this task under D3's "keep the guard"; it is the one new refusal and the reviewer should read it first.
- **The guard** (`test_every_order_passes_the_reconciliation.py`): the session opens in one place that reads the account first; every live order needs the session open (the handler's first gate); `ensure_ready()` is called from the three actions and the command handler only; every file that sends `submit(..., live=True)` is declared with how it is covered. Mutation-verified: removing the `opens_session` condition, the Start call or the Arm call turns tests red.
- **UI.** The Trade mode lost Enable live trading (command, toolbar button, confirmation, `ask_to_enable`); `DeskSessionControls` keeps Emergency stop; a desk's chart goes live on the session-opened event; the Bots Arm/Disarm commands no longer wait for trading to be off; the banner's "Trading is OFF" alignment state is removed (`compute_venue_alignment` raises for a venue that places no orders).
- **A venue with no key is quiet (a consequence of 034B, found here).** Every venue is assembled, so a desk exists for a venue the person gave no key; its account reads raise inside the dispatcher, which logs ERROR. A desk now asks `KeyCheck` (`trading/ui/desk/venue_key.py`, the credentials provider read per call) and says "No API key for … " instead of reading; Emergency stop skips a venue with no key and no open session. Without this every start of the app logged six errors and the gate's log scan would fail.
- **Names kept on purpose.** `TradingSwitchChangedEvent`, `ExecuteOrderSafetyGate.TRADING_SWITCH_OFF` and `OwnerBudgetRefusal.TRADING_SWITCH_OFF` still carry the switch's name; EPIC-034A/D/G run in parallel and touch their consumers, so the rename waits for the epic's end. Their words to the user changed.
- **Not built.** D3's mainnet confirmation: no mainnet `TradingVenue` exists, so there is nothing to attach it to (`EPIC-026`).
- **Known limit, for the coordinator.** A bot restored at start (RECOVERING) resumes when the session opens (`BotEventRouter.on_switch`); with no switch that is the next start, arm or manual order, so a restored bot waits until then. A boot-time `ensure_ready` for venues with recoverable bots, off the UI thread, would close it; not done, since it opens a session without a user action.
