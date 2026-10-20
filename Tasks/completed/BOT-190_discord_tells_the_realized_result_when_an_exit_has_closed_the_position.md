# BOT-190 — Discord tells what an exit realized once the position is closed

**Status:** ✅ Done (2026-10-20)
**Board:** Decision: the realized result of an exit is told from a bots-side event, `BotExitClosedEvent`, published right after the booking of the exit slice that leaves the run holding dust, because STOPPED is entered before the slices fill and no signal in the status report says the close is finished (option A, owner 2026-10-20); one INFO `EXIT_CLOSED` per run. PR #591 (alerting-only trigger) closed unmerged.
**Source:** `PRO-015` §2.3 asked for "price, position closed, realized loss"; `BOT-189` review round 1 (PR #572) found the exit message goes out before the close is known. Owner decision of 2026-10-20 (the coordinator's recommendation, option A): the bots side publishes one small contract event once the exit's last slice is booked.
**Risk:** 🟡 — a notification published after a booking on the close path of a real-money bot; it orders, cancels, sizes and confirms nothing.
**Complexity:** S — one contract event, one publish point after `book_exit_fill`, one alerting source, one catalog row.
**Depends on:** `BOT-189`.

---

## 1. Context and problem
The exit alert goes out on the entry into STOPPING (`BotAlertSource._alert_on_exit`). The market sell that closes the position fills later: `GridStopSequence._confirm` moves the bot to STOPPED right after the exit slices are *sent*, and each slice's fill is booked afterwards by its own fact on the bot's queue (`GridFacts._apply_fill` → `book_exit_fill`). Measured on the fake exchange (Spot Testnet, a stop loss at 39,000 after ladder buys) by the author of PR #591:

| Moment | Inventory | Run total |
| :--- | :--- | :--- |
| Entry into STOPPED | 0.03215781 | -345.52 |
| After the first exit slice is booked | 0.02143781 | -242.06 |
| Final (all slices booked) | 0.00000781 (dust below the lot) | -35.23 |

So neither the state change nor "inventory dropped" (wrong figure after slice one) nor "inventory is zero" (dust stays) tells that the close is finished. Only the bot, after it booked the last slice, can.

## 2. Acceptance criteria
- [x] A bot that stopped for `stop_loss`, `take_profit` or `range_exit` sends one INFO message once the exit's last closing slice is booked, with the run's result from its books (the exit's fee and fill price included), the profit of its completed cycles and their number. *Evidence:* `test_a_stop_loss_tells_the_result_the_books_hold_once_its_last_slice_is_booked` (composed app over the fake exchange, a four-slice exit): the message's total equals the run's books after the last fill and differs from the total at STOPPED; red when the event is published at the first slice (`-330.22` against `-58.52`).
- [x] A stop the owner asked for sends none, whether it sells or keeps. *Evidence:* `test_a_stop_the_owner_asked_for_sends_no_result_whether_it_sells_or_keeps`; `test_a_stop_that_is_not_one_of_the_three_exits_tells_no_result`.
- [x] One message per run; a repeat is not a second message and two runs are two. *Evidence:* `test_each_run_is_its_own_message_and_a_repeat_of_one_event_is_the_same_key`; the journey counts one message across the four slices.
- [x] Covers the Futures reduce-only close. *Evidence:* `test_the_reduce_only_close_tells_the_exit_once_with_the_books_after_its_last_fill`.
- [x] Nothing the bot orders, cancels, closes, sizes or when it confirms changes; `GridStopSequence` and the exit slicing are untouched. *Evidence:* the diff touches no file under `stop/` or `services/positions/`; the existing bots tests are unchanged and green.

## 3. Design
- **Publish point.** `GridFacts._apply_fill`, right after an exit slice's fill is booked (`book_exit_fill` + commission), calls `GridExitReport.after_exit_fill`. It reads the books: if what the run still holds is dust it publishes `BotExitClosedEvent` (`bot_id`, `run_id` = bot id and the moment the run started, the stop's reason, the Total PnL, grid profit, cycles, unpriced fees). The figures come from `pnl_summary`, the function behind the Bots tab's Total PnL, so the message and the screen agree.
- **Dust, as the stop treats it.** `is_exit_dust`: under one market step (neither close can send less), and on Spot also worth less than the venue's minimum notional (`SpotExposureCloser` keeps such a base). A position venue's reduce-only close ignores the notional, so only the step judges there.
- **Once per exit.** `OffLadderOrders.exits_sent` counts the slices sent; an exit is told once per growth of that count, so more trades of the last slice publish nothing, and a later exit of the same run (a halt that closed, then a stop loss) is told again.
- **Alerting decides who hears.** The bots event is kind-neutral and carries the reason; `BotExitAlertSource` tells only `EXIT_ON_STOP` reasons (the split from PR #591: `bot_exit_words.py`), so a stop the owner asked for, a halt and the exchange-side stop send nothing here. The dedup key is the run (`run_id`), the review question of PR #591.
- **Rejected:** a trigger in alerting from the status report (PR #591: pre-close mark-to-market), a 1% inventory heuristic (option B), wording it as "so far" (option C).
- **Limits, said.** An exit that sold nothing (a base kept as dust) books no fill and publishes nothing. A restart in the middle of an exit forgets the slices it sent (`OffLadderOrders` is in memory), so that exit is not told; the entry message already went out.

## 3a. Reuse
`used` `BotFillAlertSource`'s shape for the new source, `pnl_summary`, `RunEarnings` and its text helpers (`total_pnl_text`, `grid_profit_text`, `cycles_text`), `Alert.raised`, `FakeExchange`/`booted` and the BOT-189 journey's fixtures; `AlertKind.EXIT_CLOSED` and `bot_exit_words.py` from PR #591. `not used`: `BotChangedEvent`/the status report as the trigger, for the reason in §1.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/events/bot_exit_closed_event.py` | New contract event. |
| `src/modules/bots/application/kinds/grid/grid_exit_report.py` | New: asks whether the exit is closed after a booking, publishes once. |
| `src/modules/bots/domain/grid/exit_dust.py` | New: the dust rule. |
| `src/modules/bots/application/kinds/grid/grid_facts.py` | The one call after an exit slice is booked. |
| `src/modules/bots/application/kinds/grid/off_ladder_orders.py` | `exits_sent`. |
| `src/modules/alerting/application/sources/bot_exit_alert_source.py` | New source. |
| `src/modules/alerting/application/sources/bot_exit_words.py`, `bot_alert_source.py` | `EXIT_ON_STOP` and the sentences moved out (PR #591), plus `closed_detail`. |
| `src/modules/alerting/domain/alert_kind.py`, `alert_catalog.py`, `module.py`, `composition/alerting_bindings.py` | `EXIT_CLOSED` (INFO, `ROUTINE`), subscription, binding. |
| `src/support/log_view/template_catalogue.json` | Regenerated for the new log call. |

## 5. Testing
Integration: the Spot journey and the owner's-stop case in `test_an_exit_tells_discord_its_result_once_the_last_slice_is_booked_on_the_fake_exchange.py`; the Futures case in `test_a_futures_grid_exits_on_the_mark_price_on_the_fake_exchange.py`. Unit: `test_bot_exit_alert_source.py`, `test_exit_dust.py`. The full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR head.

## 6. Docs touched
`Docs/MODULES/bots/03-context.md`, `06-runtime.md`; `Docs/MODULES/alerting/03-context.md`, `05-building-blocks.md`, `06-runtime.md` (the sequence: the event after the last booking), `08-concepts.md`.

## Implementation notes
- The Spot journey's fake delivers the stream between slices, so all four slices are booked inside one `_tick`; the proof of ordering is that the total at STOPPED (captured from `BotChangedEvent`) differs from the final books, and that publishing at the first slice is red.
- The old trigger (the message built from the entry into STOPPED) fails the same assertion: its figure is the STOPPED-time total.
