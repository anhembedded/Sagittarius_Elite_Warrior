# BOT-190 — Discord tells what an exit realized once the position is closed

**Status:** ✅ Done (2026-10-19)
**Priority:** P3
**Board:** An exit's message went out when the stop began and could not carry the result; the alert source now remembers a stop that began as an exit and sends one INFO `EXIT_CLOSED` when the bot is STOPPED, with the run's result and cycles read from the status report's `earnings`. A stop the owner asked for sends none. No stopper code changed.
**Source:** `PRO-015` §2.3 asked for "price, position closed, realized loss"; `BOT-189` review round 1 (PR #572) found the message goes out before the close is known. Recommended by the author, awaiting the owner's yes.
**Risk:** 🟢 — reads and reports only.
**Complexity:** S — one more entry in `BotAlertSource` (entry into STOPPED with an exit reason) and a figure on a bots contract (the status report holds no profit by design).
**Depends on:** `BOT-189`.

---

## 1. Context and problem
The exit alert is sent on the entry into STOPPING (`bot_alert_source.py` → `BotAlertSource._alert_on_exit`). The market sell that closes the position fills later; its result is in the run's books, not in the status report.

## 2. Acceptance criteria
- [x] A bot that stopped for `stop_loss`, `take_profit` or `range_exit` sends one INFO message on entering STOPPED with the run's realized total and cycles.
- [x] A stop the owner asked for sends none.

## 3. Design
Not written. The task assumed the figure had to be published by the stopper; it does not: since `BOT-192` the status report's `BotStatusEntry.earnings` (`RunEarnings`) carries the run's account, so alerting reads it on the entry into STOPPED and no stop code changes.

## 3a. Reuse
`BotAlertSource`, `Alert.raised`, the run's books (`GridRuntime.realised_profit`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/domain/alert_kind.py`, `alert_catalog.py` | `EXIT_CLOSED`, INFO, `ROUTINE` group |
| `alerting/application/sources/bot_alert_source.py` | remember a stop that began as an exit (also at seed, for a restart mid-stop); on STOPPED publish one `EXIT_CLOSED`; forget it when the stop ends elsewhere |
| `Docs/MODULES/alerting/06-runtime.md`, `08-concepts.md` | the new message and kind |

## Implementation notes (written when done)
The message words the run's result from `total_pnl_text` / `grid_profit_text` / `cycles_text` (the Bots tab's and `bot show`'s own words), so an unjudged result reads "—", never zero. The memory is in the source, keyed by bot id, set on the entry into STOPPING with an exit reason (`EXIT_ON_STOP`) and on seed; a stop that ends HALTED or ERROR drops it, so a later unrelated STOPPED tells nothing. Filed `BUG-232` (the system display time zone falls back to UTC) from the review of `BOT-181`.
