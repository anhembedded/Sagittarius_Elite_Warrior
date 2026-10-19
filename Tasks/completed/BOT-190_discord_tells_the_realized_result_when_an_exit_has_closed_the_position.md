# BOT-190 — Discord tells what an exit realized once the position is closed

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** `BOT-189` tells a stop loss, a take profit or a closing range exit when the stop starts, so the message cannot carry the realized result; one INFO on entering STOPPED for an exit reason would carry the run's realized total.
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
