# EPIC-044B — A Grid started away from its range waits in `AWAITING_RANGE` and lays its ladder when the price enters

**Status:** 🟡 In progress
**Source:** the owner, 2026-10-21, through the coordinating session (quoted once in the epic README: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"* — if the price is out of the range the bot still starts but only begins laying orders once the price is inside).
**Risk:** 🔴 — it changes what a real-money bot does at Start, in every direction and on both markets, and adds a lifecycle state.
**Complexity:** L — the lifecycle table, the start path, the entry watch, the checks, the restore row and the red-before tests of every direction × side.
**Epic (optional):** [EPIC-044](../README.md)
**SPEC (optional):** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-044A](EPIC-044A_the_decision_record.md) accepted; for the Futures restart test, the separate VPS bug fix

---

## 1. Context and problem
The ADR's D1–D9 and D12. Established on `849d973`: five behaviours depending on direction and side, one of which (SHORT above the range) market-shorts the whole capital while the check says otherwise.

## 2. Acceptance criteria
- [x] **Red first.** On `849d973` a test shows a SHORT started above its range plans a market short of the BUY levels' quantity and that its verdict says "BUY orders only"; the PR says so plainly.
- [x] For each of LONG, SHORT, NEUTRAL × price below and above the range, on Spot (LONG) and Futures: Start leaves the bot `AWAITING_RANGE` with **zero orders** placed and no opening trade; a later in-range tick lays the ladder the plan gives at the entry price, including the opening buy or short.
- [x] The entry decision uses the mark on Futures and the last trade on Spot; the bounds are inside; a trigger the fresh book read contradicts lays nothing and changes no state.
- [x] `PRICE_BELOW_RANGE` / `PRICE_ABOVE_RANGE` are informational (`OK`), direction-free, say "starts waiting for the price to enter X–Y (now Z)", and block nothing; the rest of the plan is judged at the nearest bound.
- [x] A restart while waiting leaves the bot `RECOVERING`, the reconcile returns it to `AWAITING_RANGE`, and nothing is laid; an unknown tagged order halts it.
- [x] Stop while waiting cancels nothing and ends in `STOPPED`; the lease and budget are released.
- [x] Stop loss and take profit (and the range-exit close) do nothing while waiting, whatever the price.
- [x] A refusal judged before entry (a REFUSED verdict, a refused budget, an order below the minimum or above the cap) halts with `entry_refused`/`ENTRY_REFUSED` and its detail; a transient cause (trading off, symbol not TRADING, rate-limit pause, unreadable price) keeps waiting, with no transition and one INFO line per episode; a refusal the start sequence meets after `range_entered` halts with its own existing reason.
- [x] The entry is confirmed by a fresh book read: a trigger the book contradicts changes no state and writes no journal row; a mark sitting on a bound for many beats produces no per-beat INFO line.
- [x] `switch_off` while waiting halts the bot; re-enabling trading lays nothing.
- [x] A Resume of a halted bot that holds nothing waits when the price is outside the range and never lays a ladder off it; inside the range it is today's Resume (`resume_plan`, no opening).
- [x] While `RECOVERING` into `AWAITING_RANGE`, a bot with `on_range_exit = CLOSE`, a stop loss it sits beyond, and a quiet feed is not closed, stopped or halted; on Futures its leverage and margin type are not judged by that reconcile (no `SETTINGS_DRIFT`).
- [x] A range-exit close skips exactly one beat after entry: entry at the bound with the mark then leaving and staying out is closed at the second beat; a mark flickering on the bound is not closed on the first.
- [x] The new guard: every hand-written state set (enum and string sets of ADR §2.4) classifies every state, and so classifies `AWAITING_RANGE`.
- [x] Mainnet and testnet behave the same (the same test over both venues).
- [x] Log lines of ADR D12 seen through the real logging configuration; `render_log_templates.py --write` run.
- [ ] The Futures restart test on the VPS path: needs the separate fix for a Futures `bot resume` refused "unexpected open positions" after a host restart (not done here; the unit test of the reconcile into the wait passes without it).

## 3. Design
The ADR §2. A new `GridRangeEntry` collaborator in `application/kinds/grid/watch/` decides on each tick; the executor posts the entry as the same `STARTING` start sequence that lays every ladder.

## 3a. Reuse
`range_position` (the one definition of inside); `AWAITING_RECOVERY`'s pattern; `GridStartSequence`, `GridHousekeeping.register`, `GridStopper`, `BotRestoreService`/`GridReconciler`; `halt_with`/`fail_with`. Not used: a new bus event (the state change carries the alert).

## 4. Changes, per file
Decided when read at implementation time; expected: `bot_lifecycle_fsm_matrix.py`, `grid_range_checks.py`, `grid_constraints.py`, `grid_executor.py`, `grid_price_reaction.py`, a new `grid_range_entry.py`, `grid_runtime.py` (`ENTRY_REFUSED`), the state sets of ADR §2.4, `Docs/MODULES/bots/state-machines.md`, `SPEC-014`, `Docs/VOCABULARY/README.md`.

## 5. Testing
The criteria above, each red before and green after, unit tier plus an integration journey over the real executor and the fake exchange; mutation-checked (flip the bound inclusion, swap the mark and the last, remove the zero-order guarantee).

## 6. Docs touched
`Docs/MODULES/bots/state-machines.md` (the new state and rows), `Docs/MODULES/bots/06-runtime.md` (the entry sequence), `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/VOCABULARY/README.md` (*Awaiting range*, *Range position*).

## Implementation notes (written when done)
Built on `849d973` after the ADR (PR #679). Evidence per criterion, all in `tests/`:

| Criterion | Proof |
| :--- | :--- |
| Red first, and the SHORT above its range | `application/services/test_grid_waits_for_the_range.py`: on `849d973` its eight "waits" cases fail on `nothing is sent to the exchange` (a SHORT at 145 sends 5 requests, among them a market SELL; a LONG at 95 market-buys), the entry cases fail on the ladder compared with a normal start. The run is in the PR body |
| Direction × side, zero orders then the normal ladder | the same file, `test_a_bot_started_away_from_its_range_places_nothing_and_waits`, `test_when_the_price_enters_the_range_it_lays_what_a_normal_start_there_would` (eight cases, Spot LONG and Futures LONG, SHORT, NEUTRAL, below and above; the entry's requests equal a normal start's at the same price), `test_a_short_started_above_its_range_does_not_sell_short_before_the_price_is_inside` |
| Entry on the mark / last trade, bounds inclusive, a book that contradicts the trigger | same file: `test_a_price_exactly_on_a_bound_enters`, `test_a_price_just_outside_a_bound_does_not_enter`, `test_a_trigger_the_book_contradicts_…` (mutation-checked: removing the fresh-book confirmation turns it red) |
| Information checks, plan judged at the bound | `domain/grid/test_grid_range_checks.py`, `test_grid_constraints.py`, `test_grid_checks.py`; `application/test_start_bot_readiness.py` (the screen and the Start handler agree: a price below the range starts) |
| Restart while waiting, unknown tagged order, watches off, no `SETTINGS_DRIFT` | `application/services/test_a_waiting_grid_survives_a_restart.py` (the control: the same drift halts a bot that was running); `tests/integration/modules/bots/test_a_grid_started_above_its_range_waits_on_the_fake_exchange.py` (the composed app over the fake exchange, real log lines) |
| Stop, SL/TP, range-exit close, switch off | `test_grid_waits_for_the_range.py` |
| Refusal and deferral at entry | `test_grid_waits_for_the_range.py` (a refused budget, a ladder under the minimum, trading off, a symbol that does not trade; mutation-checked: removing the budget registration turns two red) and `test_a_waiting_grid_asks_the_readiness_and_skips_one_beat.py` (the readiness refusing and deferring) |
| Flat Resume | `application/services/test_a_flat_resume_waits_for_the_range.py` (HALTED and AWAITING_RECOVERY, below and above, SHORT/NEUTRAL, the automatic recovery, and the controls: inside the range, and a bot that holds inventory) |
| One skipped beat | `test_a_waiting_grid_asks_the_readiness_and_skips_one_beat.py` (mutation-checked: skip removed turns both red) |
| The guard | `architecture/test_every_state_set_classifies_every_state.py` and `state_set_classification.py` (21 sets, enum and string; adding a state turns it red) |
| Mainnet = testnet | `test_grid_waits_for_the_range.py::test_mainnet_and_testnet_wait_and_enter_the_same_way` |
| Log lines | the integration test asserts `[range-wait]` and `[range-entry]` through the app's logger; `src/support/log_view/template_catalogue.json` regenerated |

Decisions taken while building, within the ADR:
- **Entry readiness is a port** (`IEntryReadiness`, `BotEntryReadiness`), because the balance and the plan's verdicts live in `BotReadinessReader`, which the executor cannot reach; it is resolved lazily in `executor_bindings.py` (the reader needs the kind catalogue these deps build). A readiness that could not read the venue defers; a refusal halts with the Bots screen's words.
- **A deferral waits 30 s** before the next attempt (`ENTRY_RETRY_AFTER_DEFERRAL`), longer than the 5 s read interval of ADR D4, because the readiness reads the account.
- **The first Start's decision uses the book price** (`_price()`), and entry decides on the exits' source (mark on Futures); the two can differ at an edge, and the entry re-reads the book (ADR D4).
- **Minimal UI so the app still starts:** every `BotLifecycleState` must have a word (`EnumLabels`), so `bot_state_looks.py` has the word "Waiting for the range" and a neutral clock; the running clock counts the wait; Stop is the only live action. The Plan banner line, the table and CLI wording, the heartbeat and the entry alert are `EPIC-044C`.
- `GridFacts._SWITCHED_OFF_FROM` gains the state (D8); the alerting reason routes gain `entry_refused` (a halt reason the owner reads in the bot's `Reason:` line).
- The grid executor was at 390 lines; the start-or-wait decision moved into `GridRangeEntry` and `GridStartSequence.run_at` to stay under the ceiling.

Not done here: the Futures restart on the VPS (the separate resume bug); `EPIC-044C` (surfaces, the entry alert and `BotRangeEnteredEvent`) and `EPIC-044D` (the replay).
