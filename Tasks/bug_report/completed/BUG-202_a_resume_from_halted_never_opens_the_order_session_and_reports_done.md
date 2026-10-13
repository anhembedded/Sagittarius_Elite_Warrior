# BUG-202 — Resume of a HALTED Grid reports "done" but the bot stays HALTED: "the budget was refused: the order session is not open"

- **Reported:** 2026-10-13 (owner, desktop app: bot `Test_real_cash`, ETHUSDT, tag `ke95g7`; relayed by the coordinator session)
- **Severity:** 🔴 P1 — a bot halted by a switch-off or an Emergency Stop can never be resumed from the app, the six orders it left rest on the exchange unmanaged, and the screen says the command worked
- **Status:** ✅ Fixed (2026-10-13)
- **Board:** Resume never opened the venue's order session (only Start, arming and a manual order do), so the resume proposal's budget registration was refused with `TRADING_SWITCH_OFF`, while the screen said "done"; fixed by making a Resume from HALTED open the session through the one path Start and the headless resume use (`order_session_opening`), behind the read-only runner and the real-money answer, and by wording a queued resume as sent, not done.
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
- `application/services/order_session_opening.py` (new): the one place a bot-side action opens the session and words the refusal. `order_session_refusal_words` is the primitive (reconcile, `refusal_words`, an `[order-session]` log line); `order_session_refusal` answers it as `VENUE_NOT_READY`. Three deliberate actions use it: Start, Resume from HALTED, and the headless `--resume-recovering`, which used to call `ensure_ready` itself and word its refusal from the raw block reason. A guard pins these callers.
- `grid_start_preconditions.py`: Start asks through the helper (behaviour unchanged, the lease is still given back); `open_session_for_resume` is the one step a Resume shares.
- `IBotRunner.resume` now answers a `BotCommandResult`, like `start`. `BotRunner.resume` opens the session for a HALTED bot before it queues, and `ReadOnlyBotRunner.resume` refuses by name first, so a read-only copy opens nothing. A session that will not open is refused, never reported as done.
- `resume_bot/handler.py` and `ResumeBotCommand.real_money_confirmed`: a HALTED resume on a mainnet venue reopens a session an Emergency Stop closed, so the use case enforces the real-money answer as Start does (`REAL_MONEY_NOT_CONFIRMED`, before any read); `command_for` sets it after the screen's question, which now says "resume this bot". A PAUSED resume opens nothing and needs none.
- `ui/bots_screen/queued_action_words.py`, `selected_bot.py`, `bots_presenter.py`: an accepted Resume of a HALTED bot, and an accepted Confirm resume, say "sent to the bot" and where the outcome shows (the log for the proposal, the Plan for why it waits); a PAUSED bot's resume and every other action keep "done". The Resume tooltip names the same places.

The open uses the bot definition's own venue. The owner's "Exchange: connected (FUTURES_TESTNET)" line is the Trade mode's market connection (`trading/ui/market/connection_words.py`), not the bot's session.

## Regression test
- `tests/integration/modules/bots/test_resume_opens_the_order_session_on_the_fake_exchange.py::test_resume_of_a_bot_halted_by_emergency_stop_opens_the_session_and_proposes` — the real path on the composed app over the fake exchange: Start, Emergency Stop (HALTED, session closed), Resume, Confirm. Failed before the fix at `assert app.scope.session_state.enabled is True` (`False`: accepted, nothing opened); passes after, with the ladder resting again. Removing the runner's open turns it red again.
- `tests/unit/modules/bots/application/services/test_resume_opens_the_order_session.py` (opens a closed session; refuses in the session's words), `test_read_only_bots.py` (a read-only resume is refused by name before anything opens), `test_resume_bot_readiness.py` (mainnet needs the real-money answer; PAUSED needs none), `test_bots_real_money.py` (the command carries it), `test_resume_recovering_for_host.py` (the host path words the refusal).
- `tests/unit/modules/bots/ui/bots_screen/test_bots_resume_status.py` and `test_queued_action_words.py` — a queued resume of a HALTED bot never says "done", a PAUSED one does; forcing the old wording turns the presenter test red.
- `tests/unit/architecture/test_every_order_is_reconciled.py::test_only_start_resume_and_the_host_resume_open_the_session_for_a_bot`.

## Verification
Architecture, bots unit and integration, shell and board guards: 4 267 passed on the revised head. Positive proof the repaired mechanism ran, from the regression test's log: `App.Bots.OrderSession - Bot trqc01: order session open (already open: False) [order-session]` on the Resume (the Start line before it reads `already open: True`). Commit tier and architecture guards: see the pull request. The `-Full` run is GitHub's.
