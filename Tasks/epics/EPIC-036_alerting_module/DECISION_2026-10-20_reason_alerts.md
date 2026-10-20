# ADR — A bot's reason chooses its alert: rate limit, rejected key, storage pause and a quiet price feed are kinds of their own

**Epic:** [EPIC-036](README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** the author session of [`EPIC-036B2`](completed/EPIC-036B2_reason_alerts_rate_limit_key_storage_price_feed.md) as an agent decision under `ONBOARDING.md` §7, within the owner's pre-approval of the coordinator's recommendations on 2026-10-20. **The owner may veto** it; a veto reverts D1–D5 (one table and its tests) and leaves `EPIC-036B` as it was.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit §1 names |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7 |

## 1. Context
✅ Established, at `1e3fb9b`: `BotAlertSource` alerts on the entry into `HALTED` or `ERROR` with the generic kind (`alerting/application/sources/bot_alert_source.py` → `ALERT_ON_ENTRY`), so an exchange rate limit (`GridReason.RATE_LIMITED`, state `HALTED`), a rejected API key (`KEY_REJECTED`, `HALTED`) arrive as `BOT_HALTED`. A bot paused because its state file cannot be saved (`STORAGE_FAILURE`, state `PAUSED`, `bots/application/kinds/grid/watch/grid_storage_watch.py` → `GridStorageWatch.pause_if_failing`) is in no alert state and reaches nobody; its orders rest on the exchange and it places nothing. A bot whose price feed went quiet halts transiently (`PRICE_FEED_STALE`, `AWAITING_RECOVERY`), which is silent on entry by decision D11 of `EPIC-042`; the one word the owner gets is `BOT_RECOVERY_STALLED`, a WARNING, after the rule's `stalled_after` (15 min default, `bots/domain/halt_recovery_policy.py` → `DEFAULT_RULE`). The kinds `RATE_LIMITED`, `KEY_REJECTED`, `STORAGE_FAILURE` and `PRICE_FEED_STALE` exist in the catalog (`alerting/domain/alert_catalog.py` → `KIND_PROFILES`) and nothing raises them. The coordinator's review of 2026-10-20 left them in `EPIC-036B` with the completeness test of the reason table. The bot's `reason_detail` for these reasons carries the failure text of a request or of the disk (`bots/application/kinds/grid/grid_order_failure.py` → `key_rejected_detail`, the `storage_failure` in `grid_storage_watch.py`), and an alert leaves the machine.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **One table, `REASON_ROUTES`, says for every `GridReason.value` how it reaches the owner**: its own kind on entry (`OWN_KIND`), its own kind when the wait stalls (`STALLED`), told by the stop path (`EXIT`), the state's generic kind (`GENERIC`) or never (`SILENT`). A reason not in the table is `GENERIC` | Accepted | 🤖 Agent decision | A new reason of a bot kind needs no change in `alerting`; a new `GridReason` that is not a row fails `test_every_bot_reason_code_is_routed_on_purpose`, so it cannot silently produce no alert or the wrong one |
| D2 | **`RATE_LIMITED` (WARNING), `KEY_REJECTED` (CRITICAL) and `STORAGE_FAILURE` (CRITICAL) replace `BOT_HALTED` / nothing on the entry into their state**; a return to `RUNNING` ends each with one "Recovered" | Accepted | 🤖 Agent decision | The catalog's own severities are used as the design gave them. A rate-limit halt was a CRITICAL `BOT_HALTED` and is now a WARNING: the bot resumes by itself after the pause the exchange named, and the owner may route a WARNING loud. The storage pause, silent until now, is told |
| D3 | **`PRICE_FEED_STALE` (CRITICAL) replaces `BOT_RECOVERY_STALLED` when the wait that stalled was on `price_feed_stale`**; the entry into the wait stays silent (`EPIC-042` D11) and the halt that says the automatic recoveries are used up stays the `BOT_HALTED` it was | Accepted | 🤖 Agent decision | The grace is the bot's own: the bot already halts after `PRICE_STALE_AFTER_SECONDS` without a tick and the recovery rule's `stalled_after` (15 min) is the wait before the owner is told. No new timer and no new number. A bot that cannot watch its stop loss is told at CRITICAL, as the hub already groups many bots losing one feed into one message and hides them behind the venue's `USER_STREAM_DOWN`. **Cost:** a feed quiet for 15 min is the first word, not the first minute; shortening it is a change of the rule's `stalled_after`, not of this table (O1) |
| D4 | **These kinds say a fixed sentence and the reason code; they copy neither the bot's `reason_detail` nor the exchange's words** | Accepted | 🤖 Agent decision | No secret, key fragment, path or exception text can reach a channel through them (`test_no_text_from_the_exchange_or_the_disk_reaches_an_alert`). The cost is that the owner reads "rate_limited" and a general sentence, not the pause in seconds; the bot's detail is in the log and on the Bots tab. The generic halt still prints the detail it always did |
| D5 | **The reason's own kind is cleared by the return to `RUNNING` only** (not by `STOPPED`, `HALTED` or `ERROR`) | Accepted | 🤖 Agent decision | A "Recovered" is sent only when the cause is gone; a bot the owner stops while its key is still rejected sends no false "Recovered". The cost is an open condition in the hub's memory until the bot runs again (bounded, in memory, `ConditionBook.MAX_OPEN`) |

## 3. Alternatives considered
- **A new source class per kind.** Lost: all four arrive as a bot's own state and reason through the one status report `BotAlertSource` already reads; four classes would each re-read the bot and keep a second copy of "the last state".
- **The kind in the bots' contract (a field on `BotChangedEvent`).** Lost: it moves alerting vocabulary into `bots`, which imports nothing from `alerting`, and changes a contract every consumer reads.
- **Copy the bot's detail into the alert as the generic halt does.** Lost for these reasons: the detail holds the failure text of a request (D4).
- **A timer in alerting for a quiet price feed.** Lost: the bot already measures the silence and parks itself; a second clock is a second truth (P5).
- **Alert on the entry into the wait for a quiet feed.** Lost: it reverses `EPIC-042` D11 (most waits end by themselves in minutes) and is the owner's call, not this task's (O1).

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Should a quiet price feed be told sooner than the recovery rule's 15 min `stalled_after` (for a Mainnet venue, say), at the cost of a message for each feed that returns by itself? | nothing | 2026-10-20 |
| O2 | Should `SystemAlertSource` (`APP_FAILURE`) keep Telegram until `EPIC-036C` moves it, or end it with the old handler? | `EPIC-036B` | 2026-10-20 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D5 | [`EPIC-036B2`](completed/EPIC-036B2_reason_alerts_rate_limit_key_storage_price_feed.md) | Built | `tests/unit/modules/alerting/application/sources/test_bot_reason_alerts.py`, `tests/integration/modules/alerting/test_a_stalled_price_feed_reaches_discord.py` |
