# BOT-197 — A manual order or a strategy arm that opens a closed order session still puts the venue's RECOVERING bots back to work

**Status:** ✅ Done (2026-10-20)
**Priority:** P2
**Board:** Decision ([ADR D3](epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-19_a_session_opened_for_one_bot_resumes_no_other.md)): a manual order or a strategy arm that opens a closed session no longer wakes the venue's `RECOVERING` bots; both pass the typed `OpenedByPerson.PERSON`, which `GridFacts._apply_switch` does not treat as a wake.
**Source:** the review of #583 (BOT-183), 2026-10-19, ADR open question O1: "A manual order or a strategy arm that opens a closed session still wakes every RECOVERING bot."
**Risk:** 🔴 — a real-money bot the owner did not resume starts laying orders because a different, manual action opened the session.
**Complexity:** S — two callers pass an opener; the owner decides the rule first.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `BOT-183` (the `opened_for` field on `TradingSwitchChangedEvent`).

---

## 1. Context and problem
`SessionReadiness.ensure_ready` publishes `TradingSwitchChangedEvent(..., opened_for=...)`. `ExecuteOrderCommandHandler` (a manual order, `ensure_ready(command.venue)`) and the strategy arm (`arm_strategy/handler.py`, `trading_session.ensure_ready()`) pass no bot, so `GridFacts._apply_switch` treats the opening as "for no bot" and reconciles every `RECOVERING` bot of the venue, as before `BOT-183`.

## 2. Acceptance criteria
- [x] The owner decides, with options: may a manual order or a strategy arm that opens a closed session wake `RECOVERING` bots? **Decided no** (the recommended option, the same rule as `BOT-183`; ADR 038 O2: a host never resumes a bot by itself): the owner's decision of 2026-10-20, relayed by the coordinator session.
- [x] Since no: the two openers name an opener that is not a bot, and a `RECOVERING` bot acts only on its own opening; a test on the composed app (a manual order opens the session, the `RECOVERING` bot stays `RECOVERING`, then resumes on its own command).

## 3. Design
Built as the candidate: a named "opened by a person, for no bot" value that `GridFacts._apply_switch` does not treat as a wake, replacing `None` for these two openers (`None` stays "no opener known").

## 3a. Reuse
`TradingSwitchChangedEvent.opened_for`, `order_session_opening`.

## 4. Changes, per file
See the implementation notes.

## 5. Testing
See the implementation notes.

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` (the paragraph on who passes `None`), the ADR `DECISION_2026-10-19_a_session_opened_for_one_bot_resumes_no_other.md` (O1).

## Implementation notes (written when done)
- **Survey of callers that pass no bot** (`ensure_ready` / `order_session_opening`): `ExecuteOrderCommandHandler` (a manual live order with `opens_session`) and `ArmStrategyCommandHandler` (arming) are the only two; both now pass `OpenedByPerson.PERSON`. Every other opener names its bot (Start, Resume, the operator's `bot stop`, and `--resume-recovering` and `--resume-halted` through the bot's own Resume). No UI enable step exists (`EPIC-034C`), and an automated order never opens a session. Nothing was left that is unsure.
- **Type:** `SessionOpener = str | OpenedByPerson | None` (`src/modules/trading/contracts/session_opener.py`), threaded through the port, `SessionReadiness`, `EnsureSessionReadyCommand`, `TradingSwitchChangedEvent.opened_for`, `IBotFacts.on_switch` and `order_session_opening`. `None` stays "no opener known" and still wakes.
- **Unchanged:** a `STOPPING` bot and a cut-short start's owed cancel (`after_switch_on`, `interrupted_start.run`) never read `opened_for`, so they still act on any opening; `--resume-recovering` sends each bot its own Resume.
- **Tests (red under mutation):** `test_a_recovering_bot_acts_only_on_a_session_opened_for_it.py`, `test_trading_switch_changed_event.py`, `test_arm_strategy_session.py`, `test_execute_order_opens_session.py`, and the composed-app `test_a_manual_order_opening_the_session_wakes_no_recovering_bot_on_the_fake_exchange.py`.
- **Log:** the `[recovering-waits]` line now names the opener ("a person" or "bot X").
