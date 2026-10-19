# BOT-189 — Discord tells the owner about every filled order, the profit of every grid cycle and every exit of a bot

**Status:** ✅ Done (2026-10-19)
**Board:** Decision: one `BotOrderFilledEvent` published from the one place a fill is settled (after the runtime is kept), one silent INFO message per full fill with the cycle's booked profit, exits told at once, fill queue bounded per channel; the exit message goes out when the stop starts (realized result: [BOT-190](backlog/BOT-190_discord_tells_the_realized_result_when_an_exit_has_closed_the_position.md)), no per-bot mute yet ([BOT-191](backlog/BOT-191_the_owner_mutes_fill_messages_per_bot.md)). PR #572.
**Source:** The owner, 2026-10-18: *"tui muốn Discord báo khớp lệnh, chốt bao nhiêu lời, v.v..."* ("I want Discord to tell me about fills, how much profit was taken, and so on"); accepted 2026-10-19 as `PRO-015` Phase 1 with *"không, bây giờ hãy làm cái task thêm thông báo trên Discord đi"* ("no, now do the Discord notification task").
**Risk:** 🟡 — the feature only reads and reports (no order or bot behaviour changes), but a busy grid fills often and Discord throttles a webhook; the bound and the CRITICAL-first order are what keep an exit alert from waiting.
**Complexity:** M — one new `bots` contract event published from one place, one alerting source, two catalog rows, one bounded-queue rule in the hub, module docs.
**Depends on:** `EPIC-036` (outbox, lanes, `BotAlertMode`, `Loudness`), `PRO-015` accepted.

---

## 1. Context and problem
`PRO-015` §1 (read at `0e072a3`): alerting only says that something went wrong. The facts exist in `bots`: a full fill is the one place `on_fill` (`src/modules/bots/domain/grid/grid_reactions.py`) emits a counter order, and `book_cycle` (`grid_books.py`) books the cycle's profit once. `STOP_LOSS_HIT`, `TAKE_PROFIT_HIT` and `RANGE_EXIT` are declared in `alert_catalog.py` and fed by nothing.

The two unknowns the proposal names, settled at `80c6c31`:
- **Do the facts reach alerting only through `bots/contracts`?** The exits do: the stop starts with the reason `stop_loss` / `take_profit` / `range_exit` and `BotChangedEvent` plus `GetBotStatusReportQuery` carry the reason and detail; `BotRangeChangedEvent` carries the range. The fill and the cycle do **not**: `BotOrderFill` is the bot's inbound copy of trading's event, and the status report holds no profit by design. So `bots` publishes one new contract event, `BotOrderFilledEvent`.
- **Discord bursts.** Not measurable here (no network to Discord). What is measured, on the fake webhook transport: the worker honours a 429's `retry_after` for the whole channel, tries a CRITICAL before any queued fill, and the fill bound holds (§5). No Discord rate is claimed.

## 2. Acceptance criteria
- [x] A bot run on the fake exchange publishes one message per **fully** filled order: bot name, symbol, side, price, quantity, level. A partial fill sends nothing. *Evidence:* `test_grid_reactions.py`, `test_grid_tells_the_app_about_a_filled_order.py`, and the composed-app journey `test_one_silent_message_per_full_fill_and_the_cycle_carries_the_profit_booked`; gate run on `32ae4ec` green.
- [x] The fill that completes a cycle also carries the cycle's net profit exactly as `book_cycle` booked it, the run's cumulative realized profit and the cycle count. *Evidence:* same tests; the journey compares the message with `runtime.realised_profit`.
- [x] A stop loss that ran, a take profit reached in the app, and the price leaving the range each send one message at once, the range one saying whether the bot holds or closes (CRITICAL when the bot closes; a hold is WARNING, see Implementation notes). *Evidence:* `test_bot_exit_alerts.py` and the journeys' stop loss, take profit and range cases. The realized result of the close is not in the message: owner-pending, [BOT-190](backlog/BOT-190_discord_tells_the_realized_result_when_an_exit_has_closed_the_position.md).
- [x] Fill messages are INFO and `SILENT`; the order id with the bot is the dedup key. *Evidence:* `test_bot_fill_alert_source.py`; the journey asserts Discord's silent flag.
- [x] Nothing is sent from a read-only copy of the data root; a restart (new app on the same data root and exchange) resends nothing. *Evidence:* the journeys' read-only and restart cases; `test_grid_reconcile_announces_kept_fills.py` (review round 1: a discarded reconcile announces nothing).
- [x] A bounded fill queue: past the bound the oldest queued fill messages are dropped and one "N fill messages skipped" line is sent; a CRITICAL alert is tried before every queued fill message. *Evidence:* `test_fill_backlog.py` (60 fills and a CRITICAL behind a 429 wait), `test_sqlite_outbox.py`.
- [x] No order, bot state or bot behaviour changes (the existing bots tests stay green unchanged). *Evidence:* `tests/unit/modules/bots` and `tests/integration/modules` green; gate run on `32ae4ec`.

## 3. Design
- **Fact in the domain, event at the edge.** `on_fill` returns the full fills it settled in `Reaction.filled` (a frozen `FilledOrder`, with the cycle profit as the difference `book_cycle` made and the run totals right after it). The executor publishes `BotOrderFilledEvent` (a `bots/contracts` event, like `BotRangeChangedEvent`) from `GridFacts._apply_fill` after `state.update`, and from the reconcile's missed-fill replay, which also settles fills the owner has not yet been told. One publisher, so no call site can forget it.
- **Source.** `BotFillAlertSource` in `alerting/application/sources/`, next to `bot_alert_source.py`, subscribed in `module.boot()` (so a read-only copy subscribes nothing). Exits are added to `BotAlertSource`: entry into STOPPING with the reason `stop_loss`/`take_profit`/`range_exit`, `BotRangeChangedEvent` when the bot holds, and the exchange-side protective stop having run.
- **Delivery safeguard in the hub, not in the source.** Kinds `ORDER_FILLED` and `FILLS_SKIPPED` in `alert_catalog.py` (group `ROUTINE`, INFO, so the default route cell is SILENT; the per-bot `BotAlertMode` would mute them, but nothing sets it yet, see Limits). `FillBacklog` (application) keeps at most `fill_backlog` queued fill deliveries per channel: it sheds the oldest, counts them, and on the housekeeping tick publishes one INFO "N fill messages skipped". `IOutbox` gains `shed_surplus`. The worker already tries CRITICAL first (`IOutbox.due`).

## 3a. Reuse
Checked `.claude/rules/capabilities.md` and `src/modules/alerting/`: no UI need (headless). Used `IAlertPublisher`/`Alert.raised`, the outbox and lanes, `NoisePolicy` dedup, `BotAlertMode`, `Loudness`, `AlertRouter`, `RecordingAlertPublisher`, `FakeAlertChannel`, `FakeWebhookTransport`, `subject_of` (moved to `sources/bot_subject.py`). Not used: the `AlertCoalescer` (one message per order was settled by the owner; it groups by kind and venue).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_filled_order.py` (new), `grid_reactions.py` | `FilledOrder` and `Reaction.filled`: `on_fill` returns the orders it filled whole with the cycle profit `book_cycle` booked and the run totals after it. |
| `src/modules/bots/contracts/events/bot_order_filled_event.py` (new) | The contract event; kind-neutral (side as text, quote asset named). |
| `src/modules/bots/application/kinds/grid/grid_fill_announcer.py` (new), `grid_facts.py`, `grid_executor.py`, `recovery/grid_missed_fills.py`, `grid_blocked_counter.py` | One publisher, called after the runtime is saved and after a reconcile applies a missed fill; a parked counter replayed keeps its fill. `grid_fill_conversion.py` (new) is a pure move of `GridFacts`' fee conversion so the file stays under the 400-line ceiling. |
| `src/modules/bots/contracts/events/bot_range_changed_event.py`, `watch/grid_range_watch.py` | `closes`: whether the bot closes outside the range or holds. |
| `src/modules/alerting/domain/alert_kind.py`, `alert_catalog.py`, `alert_policies.py` | `ORDER_FILLED`, `FILLS_SKIPPED`; `DeliveryPolicy.fill_backlog` (25). |
| `src/modules/alerting/application/sources/bot_fill_alert_source.py`, `bot_subject.py` (new), `bot_alert_source.py` | The fill source; the exits (stop/take profit/range exit on entry into STOPPING, the range event of a holding bot, the exchange stop having run). |
| `src/modules/alerting/application/fill_backlog.py` (new), `alert_hub.py`, `contracts/i_outbox.py`, `adapters/sqlite_outbox.py` | The bound and the one "N fill messages skipped" line; `IOutbox.shed_surplus`. |
| `src/modules/alerting/module.py`, `composition/alerting_bindings.py` | Subscribes and binds the new handlers; none on a read-only copy. |
| `Docs/`, `Tasks/proposal/PRO-015.md` | §6. |

## 5. Testing
| Criterion | Proof |
| :--- | :--- |
| One message per full fill, none for a partial fill | `tests/unit/modules/bots/domain/grid/test_grid_reactions.py` (reaction level); `tests/unit/modules/bots/application/services/test_grid_tells_the_app_about_a_filled_order.py` (executor); `tests/integration/modules/bots/test_a_bot_tells_discord_about_every_fill_cycle_and_exit_on_the_fake_exchange.py::test_one_silent_message_per_full_fill_and_the_cycle_carries_the_profit_booked` (the composed app, a real bot on the fake exchange, the real Discord channel over a fake transport). |
| The cycle message carries the profit `book_cycle` booked | same three; the integration test compares the message with `runtime.realised_profit`. |
| Stop loss, take profit, range exit | `tests/unit/modules/alerting/application/sources/test_bot_exit_alerts.py`; the integration test's stop loss, take profit and range journeys. |
| INFO and silent; dedup key is bot and order | `test_bot_fill_alert_source.py`; the integration test asserts Discord's silent flag. |
| Nothing from a read-only copy; a restart resends nothing | the integration test's read-only and restart journeys (the restart tells a fill missed while closed exactly once and not the earlier one). |
| Bounded queue; a CRITICAL is not delayed | `tests/unit/modules/alerting/application/test_fill_backlog.py` (60 fills + 1 CRITICAL behind a 429 wait: the CRITICAL is the first message after the wait, then the newest 25 fills and "35 fill messages skipped"); `test_sqlite_outbox.py::test_shedding_a_surplus_keeps_the_newest_of_one_kind_on_one_channel`. |
| No behaviour change | `tests/unit/modules/bots`, `tests/integration/modules` unchanged and green (5,492 passed with the alerting and operations unit tests). |

Mutation checks (`testing-rule.md` §2): 15 single-line mutations each turned a test red: the announce call removed; a partial fill announced; the cycle profit's sign; the oldest instead of the newest kept; the trim removed; the subscription removed; the `closes` guard removed; the order id dropped from the key; the missed-fill announce removed; the `take_profit` row removed; the exit hook removed; the skipped line removed; the range condition's key; fills made CRITICAL; a parked fill's announcement dropped. The real-app journey also caught a bug the unit tests had missed (the range condition was cleared under a key it was never opened under).

## 6. Docs touched
`Docs/MODULES/alerting/` (03-context, 05-building-blocks, 06-runtime, 08-concepts, 10-quality as the facts change), `src/modules/alerting/module.py` docstring, the headless runbook, `Docs/VOCABULARY/README.md`, `Tasks/proposal/PRO-015.md`.

## Implementation notes (written when done)
- **The two unknowns.** Settled in §1. The measured part is the fill bound, on the fake channel; the Discord limit itself is not measured and is not claimed.
- **Decisions taken** (all reversible, notification-only, no real-money behaviour): the exit message is sent when the stop *starts*, so it says the bot is closing at market; the realized loss of that close is not known then and is not in the message (`PRO-015` named it; the status report holds no profit by design); awaiting the owner's yes, or a follow-up INFO on entry into STOPPED carrying the run's realized total. A range exit that closes is CRITICAL, one that only holds is the catalog's WARNING (silent unless routed loud; PRO-015 said loud: awaiting the owner's yes). The return inside the range is not told; a price flapping at the edge is bounded by the hub's 15 minute window (one message per side), after review round 1 showed a "Recovered" per crossing was unbounded. The price in a fill message is the order's own (limit) price; a limit order fills at it or better.
- **Limits.** (1) Nothing yet lets the owner mute fills per bot: `AlertSettings.bot_modes` exists but no page or file sets it (settings are in memory, `EPIC-036D`), so fill messages go out for every bot; Discord's channel mute is the control today. (2) The hub's dedup windows are in memory; a restart sends nothing again because the bot counts a fill once, not because the hub remembers it. (3) Quiet hours hold fill messages like any INFO and fold them into the summary.
- **Delivery.** Draft pull request #572 from `claude/discord-fill-notifications`, head `32ae4ec` (then this record's move). `ci-local.ps1 -Full` green on `32ae4ec` (gate Unit, gate Rest); independent review rounds 1-3, the last PASS, with round 1's findings (reconcile announced before its runtime was kept; the range flap; task drift) fixed. Not merged: the owner merges, and may veto the two pending decisions, which are filed as BOT-190 and BOT-191.
