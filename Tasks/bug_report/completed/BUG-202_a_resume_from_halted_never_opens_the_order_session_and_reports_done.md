# BUG-202 — Resume of a HALTED Grid reports "done" but the bot stays HALTED: "the budget was refused: the order session is not open"

- **Reported:** 2026-10-13 (owner, desktop app: bot `Test_real_cash`, ETHUSDT, tag `ke95g7`; relayed by the coordinator session)
- **Severity:** 🔴 P1 — a bot halted by a switch-off or an Emergency Stop can never be resumed from the app, the six orders it left rest on the exchange unmanaged, and the screen says the command worked
- **Status:** ✅ Fixed (2026-10-13)
- **Board:** Resume never opened the venue's order session (only Start, arming and a manual order do), so the resume proposal's budget registration was refused with `TRADING_SWITCH_OFF`, while the screen said "done"; fixed by making a Resume from HALTED open the session through the one path Start uses (`order_session_refusal`) and by wording a queued resume as sent, not done.
- **Context:** Bots → Resume from HALTED ([SPEC-004](../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md): the session opens by a deliberate action) → `src/modules/bots/application/use_cases/resume_bot/`, `application/services/grid_resume_sequence.py`, `ui/bots_screen/bots_presenter.py`
- **Environment:** Desktop app, Spot venue, bot HALTED (`SWITCH_OFF`) with its ladder resting; the exchange-facts read succeeded (4 own and 0 other orders). Reproduced on the fake exchange in the composed app.

## Reproduction
1. Start a Grid; run Emergency Stop on its venue: the bot is HALTED, the order session is closed.
2. Press Resume. Expected: the session opens, the bot proposes a ladder to confirm. Actual: the command is accepted ("Resume …: done"), the bot stays HALTED with "resume waits: the budget was refused: the order session is not open", and Confirm resume is refused for lack of a proposal. Every time.

## Symptom
Plan panel: "Halted — resume waits: the budget was refused: the order session is not open". Status bar after the click: "Resume Test_real_cash: done". Log: `Saved bot ke95g7 (HALTED)`. Pause is disabled, which is correct for HALTED.

## Root cause
The order session closes by Emergency Stop or a switch-off and opens only by a deliberate action that calls `ITradingSession.ensure_ready()` (`EPIC-034C`). Start does (`grid_start_preconditions.py`, the `order_session_refusal` call), as do arming a strategy and a manual order. Resume from HALTED did not: `ResumeBotCommandHandler.execute` queued `runner.resume`, whose worker runs `GridResumeSequence.propose`, whose first step `GridHousekeeping.register()` (`grid_resume_sequence.py:119`) asks trading for the budget; trading refuses it while the session is closed (`register_owner_budget/handler.py:158`). `propose` then wrote the "resume waits" detail and returned `None`, on the worker, after the use case had already answered accepted; `BotsPresenter._on_finished` turned accepted into "done" (`bots_presenter.py:341`). Two defects, one cause each: the missing open, and a status word that claims an outcome the queued command had not reached.

Not a regression of #490: the `register()` call and the Start/Resume asymmetry are older; the gap opened when `EPIC-034C` removed the Enable trading switch and moved "open the session" into the actions that start trading, and Resume was not one of them.

Family scan (every caller of `register_owner_budget` / `GridHousekeeping.register`): Start (opens), the opening buy's count (inside a Start that opened), the reconciler, the risk read and the stop sequence's retries. The last three are automated callers and must not open the session ("a late order cannot undo an Emergency Stop", `ITradingSession.ensure_ready`); the stop sequence already waits in STOPPING for trading to be on (`WAITING_FOR_TRADING`) and says so. So Resume from HALTED is the only user action that registered a budget without opening the session. A PAUSED bot's resume lays no ladder and registers nothing, so it is left alone.

## Fix
- `application/services/order_session_opening.py` (new): `order_session_refusal(session, bot_id)`, the one place a bot action opens the session and words the refusal (`VENUE_NOT_READY`, `refusal_words`), with an `[order-session]` log line.
- `grid_start_preconditions.py`: Start now asks through it (behaviour unchanged, the lease is still given back on a refusal): one path, not a copy.
- `resume_bot/handler.py`: a resume from HALTED opens the session after the readiness refusals that cost nothing and before it queues; a session that will not open is refused here in the session's own words, with nothing queued. The handler takes `IVenueTradingPorts` (auto-resolved by the container).
- `ui/bots_screen/queued_action_words.py` (new) and `bots_presenter.py`: an accepted Resume or Confirm resume says "sent to the bot" and where its outcome shows; every other action keeps "done".

Mainnet: the Resume click already passes the real-money question (`_STARTS_TRADING` in `bot_commands.py`), so opening the session there is as deliberate as a Start.

## Regression test
- `tests/integration/modules/bots/test_resume_opens_the_order_session_on_the_fake_exchange.py::test_resume_of_a_bot_halted_by_emergency_stop_opens_the_session_and_proposes` — the real path on the composed app over the fake exchange: Start, Emergency Stop (HALTED, session closed), Resume, Confirm. Failed before the fix at `assert app.scope.session_state.enabled is True` (`False`: the command was accepted and opened nothing); passes after, with the ladder resting again.
- `tests/unit/modules/bots/application/test_resume_bot_readiness.py::test_a_resume_from_halted_opens_the_order_session_before_it_is_queued` and `::test_a_resume_whose_session_will_not_open_is_refused_not_reported_done`; the PAUSED test now also asserts no open.
- `tests/unit/modules/bots/ui/bots_screen/test_queued_action_words.py` — a queued resume never says "done".

## Verification
Bots unit and integration tiers: 3 280 passed before the new unit tests; the new tests pass. Positive proof the repaired mechanism ran, from the regression test's log: `App.Bots.OrderSession - Bot trqc01: order session open (already open: False) [order-session]` on the Resume (the Start line before it reads `already open: True`). Commit tier and architecture guards: see the pull request. The `-Full` run is GitHub's.
