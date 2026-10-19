# BOT-190 — Discord tells what an exit realized once the position is closed

**Status:** 🟡 Blocked: owner decision on a bots event after the last exit slice (options A-D below)
**Priority:** P3
**Board:** Blocked: an exit's result can only be told once its last closing slice is booked, which only a bots-side event after that booking can say; alerting alone cannot (measured below). The owner decides between the options A-D in this file.
**Source:** `PRO-015` §2.3 asked for "price, position closed, realized loss"; `BOT-189` review round 1 (PR #572) found the message goes out before the close is known. Recommended by the author, awaiting the owner's yes.
**Risk:** 🟢 — reads and reports only.
**Complexity:** S — one more entry in `BotAlertSource` (entry into STOPPED with an exit reason) and a figure on a bots contract (the status report holds no profit by design).
**Depends on:** `BOT-189`.

---

## 1. Context and problem
The exit alert is sent on the entry into STOPPING (`bot_alert_source.py` → `BotAlertSource._alert_on_exit`). The market sell that closes the position fills later; its result is in the run's books, not in the status report.

## 2. Acceptance criteria
- [ ] A bot that stopped for `stop_loss`, `take_profit` or `range_exit` sends one INFO message on entering STOPPED with the run's realized total and cycles.
- [ ] A stop the owner asked for sends none.

## 3. Design
Not written. The figure must reach alerting through a `bots/contracts` fact (an event published by the stopper at the end of the stop), not the status report.

## 3a. Reuse
`BotAlertSource`, `Alert.raised`, the run's books (`GridRuntime.realised_profit`).

## 4. Changes, per file
Written when the task starts.

## Blocked (2026-10-19): alerting alone cannot know the exit is finished
PR #591 built this from alerting only and was closed unmerged (branch `claude/bot-190-discord-realized-result` kept). Review round 1 found, and a measurement on the fake exchange confirmed, that the STOPPED state is entered **before** the closing sells fill: `GridStopSequence._confirm` transitions to STOPPED right after the exit slices are sent, and each slice's fill is booked later by a separate task on the bot's queue (`GridFacts._apply_fill` → `book_exit_fill`). The status report's `earnings` at STOPPED therefore still holds the position and is the pre-close mark-to-market.

Detecting the booking from the status report does not work either, on the measured run (Spot Testnet fake, a stop loss at 39,000 after several ladder buys):

| Moment | Inventory | Run total |
| :--- | :--- | :--- |
| Entry into STOPPED | 0.03215781 | -345.52 |
| After the first exit slice is booked | 0.02143781 | -242.06 |
| Final (all slices booked) | 0.00000781 (dust below the lot) | -35.23 |

"Inventory dropped" fires after the first slice with a wrong figure (-242.06 for a final -35.23), and "inventory is zero" never fires because dust below the lot size stays. The exit is sold in several slices, so no signal derived from the status report says it is finished.

Options (the author's recommendation is A):
- **A.** `bots` publishes one small contract event (e.g. `BotExitClosedEvent`) from the exit-fill booking, once the last exit slice of a stop is booked; `BotAlertSource` turns it into the INFO `EXIT_CLOSED` message with the run's result. Exact. It edits the close/exit booking path (`grid_facts.py`, `off_ladder_orders.py`), reading the books after a fill and sending nothing, but it is close code on a real-money path, so it needs the owner's yes.
- **B.** A heuristic in alerting: fire when the remaining inventory is under 1% of what was held at STOPPED. No bots change, approximate, and misses when the lot step leaves more than 1%.
- **C.** Tell the exit at STOPPED but word it as "closing; result so far". Meets no "realized" criterion.
- **D.** Drop the task.

The work of PR #591 that stays valid and is worth reusing for A: `AlertKind.EXIT_CLOSED` (INFO, `ROUTINE` group), the words (`bot_exit_words.py`), memory of a stop that began as an exit across a restart, per-run dedup, and a test on the fake exchange that compares the message's total with the run's final books.
