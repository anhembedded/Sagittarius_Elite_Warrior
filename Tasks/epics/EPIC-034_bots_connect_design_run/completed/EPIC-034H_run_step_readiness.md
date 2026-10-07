# EPIC-034H — Run: one readiness query serves the screen and the Start handler; Save and Start

**Status:** ✅ Done (2026-10-07)
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — the last gate before orders
**Complexity:** M — a query, the progress panel, the primary action
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034C](EPIC-034C_trading_switch_folded_into_actions.md), [EPIC-034F](EPIC-034F_design_step_constraints.md)

---

## 1. Context and problem
Five Start refusals surface only after the click (`grid_start_preconditions.py:68-109`), and "Save the changed parameters first" is never shown (`bot_action_rules.py:75-76`).

## 2. Acceptance criteria
- [x] A `GetBotReadiness` query returns the three steps and every remaining item with its reason and its fix; the Start handler calls the same query before any order, so the screen and the handler cannot disagree.
- [x] The Bots mode shows the three steps' progress; each missing item has a fix action (focus the field, Save, Retry).
- [x] "Save and Start" is the primary action (D8), disabled with "N things left" that leads to the list; the other lifecycle actions stay in the Bots menu.
- [x] No Start refusal appears after the click that was not shown before it, except a race the handler reports in the same words.
- [x] SPEC-014 is updated; its "Proven by" tests cover the three steps.

## 3. Design
The readiness FSM started in `EPIC-034D` is completed here, with the Connect, Design and Run states in one matrix file. The query composes the snapshot, the assertions and the run preconditions; nothing is checked in two places. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/queries/` | the readiness query |
| `src/modules/bots/application/use_cases/start_bot/` | calls it |
| `src/modules/bots/ui/bots_screen/` | progress, primary action |
| `Docs/SPEC/SPEC-014*` | updated |

## 5. Testing
Unit: the handler refuses exactly what the query reports, red first by bypassing it. An integration journey from a new bot to a running bot through the three steps. Desktop E2E. A reviewer is required. Not run.

## Implementation notes (written when done)
**Delivered** on branch `claude/epic-034-pr5-design-run-live-chart` (PR-5, after `EPIC-034F`).

| Criterion | Evidence |
| :--- | :--- |
| One `GetBotReadiness` query returns the three steps and every item with reason and fix; Start calls the same before any order | `GetBotReadinessQuery`/`Handler` over `BotReadinessReader`; the one function is `assess_readiness` (`services/readiness_assessment.py`). `StartBotCommandHandler` asks the reader under `BotCommandLock`, before any order and before saving. `test_start_bot_readiness.py::test_start_refuses_exactly_what_the_query_reports` for three breakages; red first: a handler that skipped the reader started a bot the query listed (mutation, 9 red) |
| Three steps' progress; each item has a fix action | `readiness_words.py`, the Plan's header, steps and items (`test_bots_run_step.py`); Bots → **Fix next item** (`FixNextItem`): read again, focus the field, or select the bot still active; `test_fix_next_*` |
| Save and Start is the primary action (D8), off with "N things left" | Start is `Save and start` in the Bots menu and toolbar; `StartBotCommand(config=…)` judges the edits as they would be saved and writes them only if the bot is ready (`test_save_and_start_with_edits_that_are_not_ready_saves_nothing`); the tip says the count and the reasons; `test_start_is_disabled_with_the_count_and_the_tip_says_what_is_left` |
| No refusal after the click that was not shown before it, except a race in the same words | The list holds Connect, Design and the Run facts that need no exchange round trip: venue, other bot, lease, budget caps. `test_a_click_refused_after_the_screen_said_ready_reads_in_the_screens_words` is the race. Two refusals remain after the click **by design** because only the exchange can answer them: reconciling the account (a foreign position) and registering the owner budget (`GridStartPreconditions`, D3) |
| SPEC-014 updated; "Proven by" covers the three steps | Steps 3–7 (Connect, Design, Blocking or advice, Run, Save and start), §5 rows, §7 and §8 |

**The readiness FSM is complete.** `bot_connect_fsm_matrix.py` became `bot_readiness_fsm_matrix.py` with six states, the Connect ones (`NOT_CONNECTED`, `CONNECTING`, `FAILED`) and the three a connected bot stands in (`DESIGNING`, `RUN_BLOCKED`, `READY`); each assessment arrives as one of `DESIGN_OPEN`, `RUN_OPEN`, `ALL_CLEAR`. `test_bot_readiness_fsm_matrix.py` holds every pair to a declared state and the assessments inert outside the connected states.

**`EPIC-034D`'s "Go live gate" Resume item is closed.** The gate was built in 034D itself (its notes record `suspend_commands`, and `test_go_live_is_not_offered_until_the_account_was_read`, `test_a_connection_that_is_lost_takes_go_live_away_again`); what 034D left to this task was Start's own refusal in the use case, which is the readiness above. Both hold after this change: the chart tests are green, and a lock still hides the same bot's chart instead of closing it.

**Decisions.**
- **One function, two callers.** The Bots screen holds the account, the market numbers and the edits already, and judging is quick, so it calls `assess_readiness` with them rather than dispatching the query on every edit; the Start path reads the same things afresh and calls the same function. The query is how anything else (a test, a script, a later screen) asks. The Run facts (venue, lease, budget) are local, so the screen reads them through one `BotRunFactsReader` too.
- **Unsaved edits are not a thing left.** Save and start saves them; Save stays for drafts. The old "Save the changed parameters first" refusal is gone.
- **The key's permission** is a Design item (the `KEY_CANNOT_TRADE` constraint), not a Connect one: the account was read, the plan cannot trade with it.
- **`ITradingSession.lease_holder(symbol)`** joined the port, with contract tests for the real and the fake session, because the lease is a refusal the user must see before the click and cannot be seen by claiming (a claim replaces the owner's own symbol). An earlier reader of the same name had been deleted when no one used it.
- **Words moved to the application.** The sentence per `ConnectionFailureKind` now lives in `services/connect_failure_words.py` so Start answers in the words the strip shows; the UI adds how to read again.
- **Start's verdict check left `GridStartPreconditions`.** The venue and verdict checks were the readiness's already; the preconditions keep only the lease claim, the reconciliation and the budget registration, which have side effects.
- **A Futures venue** is named once, in the Run step ("… is not a Spot venue this app trades on"), and Design waits; an unreachable venue is Connect's item and not repeated.

**Verification.** Commit tier PASS (log below); `tests/unit/architecture` green; `tests/unit/modules/bots`, `tests/unit/modules/trading` and `tests/integration/modules/bots` run by hand; mutation checks on the handler (readiness skipped; edits not passed to the readiness), the lease (own claim counted) and the assessment (lease item dropped), each turning a named test red. Desktop E2E on a real display and the owner's own run on Testnet: **not run**.
