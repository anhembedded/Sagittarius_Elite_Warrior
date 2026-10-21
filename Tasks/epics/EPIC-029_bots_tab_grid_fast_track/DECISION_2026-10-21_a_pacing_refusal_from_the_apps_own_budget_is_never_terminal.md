# ADR — A pacing refusal from the app's own order budget is "not yet" for a bot, not a terminal start refusal (one exception: D3)

**Epic:** [EPIC-029](README.md)
**Date:** 2026-10-21
**Status:** Proposed
**Decided by:** Pending the owner: it changes what a bot does with real money (a position kept instead of closed), so it is not a default under `ONBOARDING.md` §7. Recommended by the author of [BUG-254](../../bug_report/completed/BUG-254_a_pacing_refusal_from_the_apps_own_order_budget_halted_a_start_and_sold_the_position.md) at the coordinator session's request (D1–D3 are its option (b); option (a) is rejected in §3).
**Supersedes / superseded by (optional):** amends, for `owner_budget_rate`, the "no safety net" line of [BUG-238](../../bug_report/completed/BUG-238_a_futures_grid_of_more_than_sixty_levels_is_halted_by_the_order_rate_cap_and_sold_at_market.md)'s fix; refines the ADR D6 checks 4 and 5 of [`DECISION_2026-10-03_bots_module_and_grid_bot.md`](DECISION_2026-10-03_bots_module_and_grid_bot.md)

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code at `970b77b` and by a test red before the change |
| 🔵 Proposed | awaiting the owner |

## 1. Context
- ✅ Four starts of one family ended in a market close of a real position because the bot's own budget refused the bot's own order: `BUG-194` (inventory), `BUG-238` (`owner_budget_rate`, 61st order), `BUG-241` (Spot exit slices: spacing and rate), `BUG-254` (`owner_budget_spacing`, twice on 2026-10-21, 0.125 and 0.136 USDT). Each fix closed the instance found; the rule stayed enforced twice, by the pacer (a forecast on the monotonic clock, `monotonic_order_pacer.py` `wait_turn`) and by trading's policy (the verdict on a stamp taken later, `handler.py` `datetime.now`, then `trading_limit_policy.py` `_owner_budget_checks`).
- ✅ The pacer cannot match the stamp: the stamp is taken after the turn, after the preview and the venue-wide submission lock, with a lag that differs per order (cold terms read on the first order after a stop, a neighbour's request holding the lock). Both owner logs fit it (`BUG-254` §Root cause). `STAMP_JITTER` margins only the rate window.
- ✅ `owner_budget_*` pacing refusals reach the bot as `REFUSED` (`order_outcome.py` `_refusal`), which a start turns into `start_refused` and a market close (`grid_order_failure.py` `_refuse`).
- ✅ Trading exempts a position owner's reducing order from spacing and rate (`trading_limit_policy.py` `_budget_checks`) and does not count a close-position stop in the book (`owner_order_ledger.py` `record_sent`).

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | Trading's verdict decides; the pacer stays a forecast. `owner_budget_spacing` reaches the bot as `PACED` ("not yet", with what was missing); the gateway takes another pacer turn and resends, up to `PACING_RETRIES` (3). | Proposed | Pending the owner | A start is no longer closed for a stamp a few milliseconds short; cost: at most three more turns (250 ms each) on a miss. |
| D2 | A rate refusal, or a spacing that kept missing, is `RATE_LIMITED` for the budget's window (the existing pause: AWAITING_RECOVERY, resumes by itself, bounded by the recovery ledger). Never `start_refused`, except D3. Amends `BUG-238`'s "no safety net". | Proposed | Pending the owner | No market close for the app's own pacing; cost: a pause up to 60 s, and the recovery re-lays the ladder, which now goes through a pacer that holds the rate across the venue. |
| D3 | The one exception: an own-budget pause that interrupts the opening after a slice filled stays a refused start that closes (`opening_outcome`). A resume re-derives the ladder from the position held and does not finish the opening, so it would run a smaller grid than the plan the owner saw; placing the stop first (tried, red/green) protects the position but not the plan. | Proposed | Pending the owner | The exception is rare (the opening's second slice missing 4 turns) and costs the old market close. Revisit when a resume can finish an opening. |
| D4 | The owner's caps (150 open orders, 60 orders a minute, 250 ms) are unchanged. `owner_budget_open_orders` is a capacity, not a pace, and stays a refusal. | Proposed | Pending the owner | No cap is loosened. |

## 3. Alternatives considered
- **(a) The bot obtains its slot from trading's book** (a reservation instead of a forecast). Loses as the only mechanism: the stamp is taken inside the venue-wide `live_submission_guard`; a reservation made outside it is racy again, and a wait inside it holds the lock that a neighbour's protective stop needs (the reason exits take no turn, `EPIC-029J1b`). It also changes trading's order gate, which another change is editing (`BUG-247`). Pattern: reservation / token bucket. It stays available behind D1 if misses persist: the verdict path is the safety net it would also need.
- **Make the pacer exact** (record the instant the sleep returned, add a margin to the spacing as `STAMP_JITTER` does for the rate). Loses: it shrinks the miss and cannot remove it, and a margin on the spacing cuts the owner's cap.
- **Keep the refusal terminal, fix each instance** (the four fixes so far). Loses: the family recurred four times.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Accept D1–D4? | merge of the `BUG-254` pull request | 2026-10-21 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D4 | [BUG-254](../../bug_report/completed/BUG-254_a_pacing_refusal_from_the_apps_own_order_budget_halted_a_start_and_sold_the_position.md) | In progress | `test_a_burst_of_orders_is_not_refused_by_the_budgets_spacing_on_the_fake_exchange.py` (red at `970b77b`), `test_bot_order_gateway_own_pacing.py`; the pull request's `ci-local.ps1 -Full` run is not yet read. |
