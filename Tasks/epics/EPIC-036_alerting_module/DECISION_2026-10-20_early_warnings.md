# ADR — Early warnings reach Discord from the events that already exist, once per condition, with a cool-down

**Epic:** [EPIC-036](README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** the author session of [`EPIC-036B1`](completed/EPIC-036B1_early_warnings_liquidation_and_user_stream.md) as an agent decision under `ONBOARDING.md` §7, within the owner's pre-approval of the coordinator's recommendations on 2026-10-20 (`REVIEW_2026-10-20_what_is_still_missing.md`, decision N5 and 026N). **The owner may veto** it; a veto reverts D1–D5 and leaves `EPIC-036B` as it was.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit §1 names |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7 |

## 1. Context
✅ Established, at `d2c7cad`: the owner runs bots unattended on a VPS and only a CRITICAL halt, error or failed stop reaches Discord. A Futures position that nears liquidation is judged by `bots/domain/grid/futures_risk_classifier.py` → `classify_risk` and published once per change of level as `BotRiskChangedEvent` (`bots/application/kinds/grid/watch/grid_risk_watch.py` → `GridRiskWatch._announce`); only its `CRITICAL` level halts the bot, and the halt is the alert. A user-data stream that is down is published per failed attempt as `UserStreamHealthEvent` (`trading/adapters/binance/user_stream_supervisor.py` → `UserStreamSupervisor`); `UserStreamWatch` halts the bots on the venue after `UserStreamLimits.down_limit` (120 s), so today a stream outage arrives as N generic bot halts. Both facts are only in the log before that. The review of 2026-10-20 deferred them to `EPIC-036B` (N5, 026N). `EPIC-036B` is large (system source, market stream, reason table, rate limit, key, storage), so the two highest-value sources are cut out of it.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **Two sources, each a thin reader of an event that exists**: `LiquidationAlertSource` (`BotRiskChangedEvent`) and `StreamAlertSource` (`UserStreamHealthEvent`). No timer, no new event, no change in `bots` or `trading` | Accepted | 🤖 Agent decision | The warnings add no order, stop or close path and no thread. They see an outage only when the supervisor reports an attempt (at most about a minute apart) |
| D2 | **Liquidation: `WARN` raises `LIQUIDATION_RISK` (WARNING); `SAFE`, a stopped bot or a removed bot ends it; `CRITICAL` and `UNKNOWN` raise nothing** | Accepted | 🤖 Agent decision | The warning distance is the bot's (`FuturesGridThresholds.liq_warn_distance`), so there is no second number to drift. The critical distance already halts the bot and the halt is a CRITICAL alert; a second message at that moment would repeat it |
| D3 | **Stream: a `CONNECTING`/`RECONNECTING` event whose outage is older than 60 s raises `USER_STREAM_DOWN` for the venue (the catalog's CRITICAL); `CONNECTED` ends it; `STOPPED` is neither** | Accepted | 🤖 Agent decision | 60 s is the notice before the bots' 120 s halt and rides out the routine 24 h reconnect (seconds). One message for the venue instead of one per halted bot. The kind keeps the severity the design gave it (infrastructure row) |
| D4 | **A cool-down of 10 min** between two raises of one bot's liquidation warning and of one venue's outage (`EarlyWarningPolicy`, `WarningLatch`) | Accepted | 🤖 Agent decision | The hub forgets its dedup window when a source clears a condition, so a flapping condition would send a pair per flap. With the latch the worst case is one pair per 10 min per bot or venue. A warning held back by the cool-down is logged. **Cost:** a second approach within 10 min of a return to safe is not told; the bot halts at the critical distance regardless. For liquidation a return to `SAFE` inside the 10 minutes leaves the warning open instead of sending a "Recovered" that a re-cross would falsify; the next `WARN` after the cool-down tells it again, and a bot that leaves the states the guard judges (halted, in error) forgets it quietly, because the guard resets silently there (review of PR #613). **Residue of the quiet forget:** no "Recovered" is sent at a halt (it would sit beside the CRITICAL halt and say the opposite), so the hub's 15-minute WARNING window and its open-condition entry stay; a `WARN` within 15 minutes of the previous one after a halt and a resume is swallowed by the hub, and the entry is overwritten by the next raise. A stopped or removed bot clears at once with "Recovered", cool-down or not |
| D5 | **The thresholds are constants of one policy object, not settings**; the defaults are `liquidation_cooldown` 10 min, `stream_down_grace` 60 s, `stream_cooldown` 10 min | Accepted | 🤖 Agent decision | No settings file, dependency or key changes. The owner can veto a number and it is one line |

## 3. Alternatives considered
- **A `LIQUIDATION_RISK` at `CRITICAL` too.** Lost: it is the halt's message again, with no new fact. The halt's `Reason:` line carries the guard's sentence.
- **A timer in the alerting module to catch a stream that sends no event.** Lost: the supervisor retries with a one-minute cap, so events are never further apart than that while it runs; a timer is a second clock to keep in step (P5). A stream that says `CONNECTED` and delivers nothing is a different fact (a silent socket), left to the periodic reconcile and the follow-up.
- **A new event from `UserStreamWatch` at the moment it halts the bots.** Lost: it needs a change in `bots` and tells the owner at 120 s what the supervisor tells at 60 s.
- **Settings for the numbers.** Lost for now (the task forbids new settings); a constant is one line to change.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Is 60 s the right notice for the stream, or should the owner be told at once for a Mainnet venue? | nothing | 2026-10-20 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D5 | [`EPIC-036B1`](completed/EPIC-036B1_early_warnings_liquidation_and_user_stream.md) | Built | `tests/unit/modules/alerting/application/sources/test_liquidation_risk_alert.py`, `test_stream_alert_source.py`, `tests/integration/modules/alerting/test_a_halted_bot_reaches_discord.py` |
