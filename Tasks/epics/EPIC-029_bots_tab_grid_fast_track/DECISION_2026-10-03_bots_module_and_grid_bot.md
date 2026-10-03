# ADR — Bots get their own module, entity and lifecycle, and the first one is a Grid bot on Spot that trading executes under an owner budget derived from exchange evidence

**Epic:** [EPIC-029](README.md)
**Date:** 2026-10-03
**Status:** Accepted (2026-10-03)
**Decided by:** The user, 2026-10-03, under `ONBOARDING.md` §7. The user accepted
[`PRO-006`](../../proposal/PRO-006.md) (*"Oki, duyệt, nhớ design đúng nha, ko lazy design"*), then
answered this record's own questions: *"D6 dùng ngân sách riêng, O5 ok, nhưng giá trị có thể thay
đổi dc. O1 ok. O2,3,4 ok."* In English: D6, use a separate budget; O5 OK, but the value must be
changeable; O1 OK; O2, O3 and O4 OK.

- D6 and D21 are 🟢 user decisions.
- O1–O5 are answered with the recommendations, and O5's value stays configurable.
- The other decisions are 🤖 agent decisions, accepted together with the design.

Review history:

- **Round 1** (PR #317, comment 5970257684) found five blocking defects and eleven others. They are
  fixed and marked **(r1)**.
- **Round 2** (comment 5970554633) found three more holes in D6 and five smaller items. They are
  fixed and marked **(r2)**.
- **Round 3** was not run before the user merged PR #317 on 2026-10-03.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

Paths in this record that do not start with `src/`, `tests/`, `Docs/` or `Tasks/` are under
`src/modules/`. T stands for `src/modules/trading`. Every ✅ line was read on `ff2a7f9a`
(2026-10-03).

## 1. Context

### 1.1 What the user asked for (🟢, from `PRO-006` §2.1)

- A **Bots** tab. Bots are designed for many from the start.
- A **fast track to one Grid bot** that places real orders on **Spot Testnet**. Mainnet stays
  behind `EPIC-026`.
- **Every bot has its own chart**, which draws that bot's own indicators.
- **A Grid's parameters belong to the user.** The bot calculates from them and reports whether
  they are reasonable. It never fixes them.
- **The Grid backtest is built in parallel** with the live bot, so Testnet does not wait for it.
- Grid comes first, because the user judges the six signal strategies to be junk. Signal bots and
  DCA come last.
- Later, the desks become manual only, with a takeover from a bot.

### 1.2 What the trading module offers a ladder of resting orders today (✅)

Line numbers were corrected after the review of PR #317 (round 1). Each was re-read on `ff2a7f9a`.

| Need of a Grid | What exists | Where |
| :--- | :--- | :--- |
| Place a LIMIT GTC order on Spot | Yes, through the venue's `IOrderSubmission.submit()`. The submission is reached through `IVenueTradingPorts.get(venue)`. | T/contracts/i_order_submission.py:71-83; T/contracts/i_venue_trading_ports.py:16-25 |
| Market BUY by quote quantity (the opening purchase) | Yes, only for a market BUY | T/adapters/binance/spot/spot_order_payload_mapper.py:98-104 |
| Choose its own client order id, or a prefix | **No.** It is always `SEW-` + 12 hex characters, generated inside trading, and the caller learns it only from the result. | T/contracts/client_order_id.py:28-40; T/application/orders/preview_order/handler.py:102 |
| Name the order's owner | Yes, `OrderRequest.owner_id` | T/contracts/order_request.py:56-87 |
| Cancel one order | Yes: `IOrderSubmission.cancel(symbol, client_order_id)`. **It is refused while the switch is off** (`TRADING_SWITCH_OFF`). | T/contracts/i_order_submission.py:111-118; T/application/orders/cancel_order/handler.py:73-81 |
| What a plain disable does to resting orders | **Nothing.** It disables the session and stops the user data stream. Orders keep resting on the exchange. | T/application/session/disable_trading/handler.py:34-39 |
| Read open orders | Account-wide only, with no symbol filter. An `Order` has no executed quantity and no exchange order id. | T/contracts/i_account_activity.py:52; T/contracts/order.py:51-71 |
| Read what an order executed, and its fees | **Executions:** `OrderRecord.executed_quantity` and `average_price` (order history). **Fees:** `TradeRecord.fee` and `fee_asset` with the exchange `order_id` (trade history). **The gap:** an `OrderRecord`'s `Order` carries no exchange order id, so today a trade's fee cannot be joined to a tagged order. | T/contracts/order_record.py:24-33; T/contracts/trade_record.py:20-37 |
| Learn of fills | `OrderFilledEvent` carries `order`, `fill_price`, `fill_quantity` (this fill only), `fee_amount`, `fee_asset` and `venue`. It is emitted by the stream adapter through the venue's event emitter, on the websocket thread. | T/contracts/events/order_filled_event.py:41-56; T/adapters/binance/spot/spot_user_data_stream.py:213-235 |
| Learn of cancels and expiries | `OrderEndedEvent(order, venue)`. The Spot parser reads only `"c"`. On a cancel, Binance documents `"c"` as the cancel request's id and `"C"` as the original order's id, so the event may name the wrong order. ❓ This is verified against the code, **not** against Binance; `EPIC-029A` proves it. | T/contracts/events/order_ended_event.py:10-29; T/adapters/binance/spot/spot_user_data_event_parser.py:70 |
| Learn that an order was accepted | **No event.** `place_order` returns the request unchanged with status NEW, and `submit()` can raise. | T/adapters/binance/spot/spot_trading_client.py:97-109 |
| Claim a symbol under its own owner | Yes: `ITradingSession.claim_symbol(symbol, owner_id)`. One symbol per owner. The holder is not queryable. | T/contracts/i_trading_session.py:134-153 |
| Query the symbol's filters and fees | Yes: `order_entry_terms.terms_for(symbol)` gives `tick_size`, `step_size`, `min_notional`, and `CommissionRate(maker, taker)` | T/contracts/i_order_entry_terms.py:53; T/contracts/commission_rate.py:18-19 |
| Learn that trading was enabled, disabled or Emergency-Stopped | **No event.** Only `ITradingSession.snapshot().enabled`. The user data stream runs only while trading is enabled. | T/contracts/i_trading_session.py:112; T/application/session/enable_trading/handler.py:134 |
| Per-order notional cap | `max_notional_per_order` is 500 and applies to every order (`src/config/app_config.json:19`). | T/contracts/trading_limits.py:89-94 |

### 1.3 The session limits stop a ladder at its second order (✅)

The limits default to these values (T/contracts/trading_limits.py:89-94):

- `max_orders_per_session=20`;
- `max_notional_per_order=500`;
- `max_positions_per_symbol=1`;
- `min_order_interval=60s`.

Every order sent marks its symbol as open (T/application/trading_session_state.py:231-236), and a
symbol counts as one open position (:218-224). On Futures the user data stream later corrects that
set. On Spot nothing ever does: the only caller of `reconcile_position_state` is
`futures_user_data_stream.py:360`.

So the **second** ladder order on a symbol is refused twice, by `MAX_POSITIONS_PER_SYMBOL` and by
`MIN_ORDER_INTERVAL`. The 21st order of the session is refused regardless.

These limits are right for what they were written for: one signal at a time on one position. They
are the wrong unit for a ladder, which keeps N resting orders on one symbol by design.

The same reading shows a gap for manual Spot trading as well. After one manual Spot order, every
later order on that symbol is refused until trading is enabled again. That is recorded as a finding
to verify in `EPIC-029A`; it is not fixed by this ADR.

### 1.4 Emergency Stop on Spot sells what was bought since the last enable (✅)

- Emergency Stop disables the switch as its step 1
  (T/application/session/emergency_stop/handler.py:146). It then cancels every open order on the
  account (:115). It then sells, at market, each asset's holding above the **baseline captured at
  the latest enable** (:224-306; T/application/session/enable_trading/handler.py:108-117).
- What that means for a bot's inventory:
  - inventory bought in the current session is above the baseline, so it is sold;
  - inventory carried from before the latest enable (after a restart or a re-enable) is inside the
    baseline, so it is **not** sold.

  After an Emergency Stop, a bot may therefore be flat, partly flat or still fully invested.
- **Its liquidation sells are untagged.** Each sell gets a fresh `generate_client_order_id()` and is
  placed directly through `trading_client.place_order` (T/application/session/emergency_stop/handler.py:276-284).
  Any inventory derived from tagged executions alone would therefore still count the coins
  Emergency Stop sold **(r2)**.
- It publishes nothing. Its result goes only to the caller (T/contracts/emergency_stop_result.py:49-54).

### 1.5 Charting and data (✅)

- **`ChartCard` is a frozen god file.** It is 881 lines and baselined
  (`tests/unit/architecture/baseline_god_files.json`), so it cannot grow. It draws:
  - candles;
  - indicator lines (`add_overlay_indicator`, `update_indicator_data`);
  - **vertical** time spans (`set_script_regions`);
  - markers (`set_script_markers`, `src/support/charting/chart_card/chart_card.py:705-760`).

  It has **no horizontal price lines**: the only one is its internal last-price line.
- **The desk's live chart cannot be reused as it is.** `ChartCoordinator` (229 lines) lives in
  `trading/ui/desk/desk_screen/chart_coordinator.py`, where another module cannot import it. It
  uses:
  - `IHistoricalKlines` for history;
  - `IMarketDataSync` to sync before reading (:47-50, :163);
  - `IMarketStream` for live candles;
  - the engine's `IThreadManager`, to run on a worker (:60, :77).
- **The tick feed is behind a frozen allowlist.** `MarketTickFeed` is in market_data's ui, and
  trading reaches it through an allowlist line that may only shrink.
- **Indicators.** ATR and Bollinger Bands do not exist. `IIndicator.update(value)` takes a single
  value, so an indicator built on high, low and close (HLC) does not fit it
  (`src/support/indicators/`).
- **Ticks.** There are no stored aggTrades. The backtest's "historical tick" run streams 1-second
  klines (`backtesting/application/run_historical_tick_backtest/handler.py:118-143`).
- **No buy-and-hold comparison** exists anywhere.

### 1.6 Conventions a new module must meet (✅)

- **Registration:** `module.py` subclasses `BoundedContextModule`, and the `MODULES` tuple lists it
  (`src/shell/modules.py:43-48`).
- **Imports:** `dependencies` must equal the contracts the module imports
  (`tests/unit/architecture/test_module_declarations.py:117`). Module-to-module imports go through
  `contracts/` only.
- **No Qt** in `domain/`, `application/` or `contracts/`.
- **CQRS:** one directory per use case.
- **Size:** 400 lines per file, ratcheted for both `src/` and `tests/` since `BOT-146`.
- **FSM:** one lifecycle per `*_fsm_matrix.py`.
- **UI:**
  - an MVP trio per screen and a `preview.py`;
  - coordinators owned by the presenter;
  - the async action fencing of `async-ui-action-rule.md`.
- **Screens** contribute through `registry.contribute_screen`. `tests/unit/shell/test_screen_wiring.py`
  pins the route map.
- **Persistence:** the only atomic-write precedent is tmp + `replace`
  (`market_data/adapters/persistence/json_symbol_catalog_repository.py:76-80`).

## 2. Decisions

Revised after the review of PR #317 (round 1). Changes from the first draft carry **(r1)**.

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **A new `bots` module** owns the Bot entity, the store, the lifecycle and the Bots screen. It depends only on `trading` and `market_data` contracts. `trading` stays the only module that sends orders. | ✅ Accepted | 🤖 agent | One more module. The guards of §1.6 apply, the vocabulary's "exactly four modules" changes, and HLD 02/03 gain a row. |
| D2 | **Bot** is a persisted aggregate: `BotId`, name, `BotKind`, venue, symbol, kind config and lifecycle state. **`BotKind` is the seam:** an ABC supplying parameter schema and verdicts, the executor factory and the chart overlay. Only `GridKind` is built. | ✅ Accepted | 🤖 agent | Signal, DCA and Futures Grid plug in later without touching the shell. Architecture rule §7.2.1. |
| D3 | **Two declared lifecycles, each in its own `*_fsm_matrix.py`, Qt-free:** the bot (§3.1, `bot_lifecycle_fsm_matrix.py`) and a Grid level (§3.2, `grid_level_fsm_matrix.py`) **(r1)**. An undeclared transition raises. | ✅ Accepted | 🤖 agent | `code/quality.md` FSM cohesion, for both lifecycles. Every transition the tasks use is in the tables, including `edit` and `delete` **(r1)**. |
| D4 | **Store:** one JSON file per bot under `state/bots/<bot_id>.json`, schema-versioned and written atomically (tmp + `replace`). It holds the definition and the bot's runtime ladder state. The store is **never** the source of the bot's inventory for any safety check; D6 derives that from the exchange **(r1)**. | ✅ Accepted | 🤖 agent | Survives restarts. A corrupted or hand-edited file can mislead the bot's display, but not a safety gate. |
| D5 | **Client order ids carry a bot tag.** `OrderRequest` gains an optional `client_order_tag`. Trading generates `SEW-{tag}-{hex10}`, where the tag is 6 characters of `[a-z0-9]` (21 of Binance's 36 characters). Untagged ids stay `SEW-{hex12}`. | ✅ Accepted | 🤖 agent | A bot recognises its own orders in account-wide reads and in history. Trading still owns id generation. |
| D6 | **Owner budget with a trading-owned owner book**, replacing the signal limits for a budgeted owner's orders. The budget, the book, and how the book is seeded and kept current are set out below this table **(r1)**. | ✅ Accepted | 🟢 user, 2026-10-03: *"D6 dùng ngân sách riêng"* ("D6: use a separate budget") | Ladders become possible while trading still bounds every bot. A bot cannot sell what it did not buy (the PR #284 class), even after a restart or a corrupted store, because its inventory always comes from exchange evidence. A runaway loop is bounded by the order-rate window. Manual and strategy orders are unchanged. |
| D21 | **`max_notional_per_order` keeps applying to bots (r1).** Every market order a bot sends is split into slices at or below the cap and spaced by the budget **(r2)**: the opening buy, stop-loss and take-profit exits, and Stop with *sell base*. The planner refuses a level whose capital exceeds the cap. With today's 500 USDT, a Grid's capital per level is at most 500, and neither the opening buy nor an exit is limited, because each is sliced. | ✅ Accepted | 🟢 user, 2026-10-03: *"O5 ok, nhưng giá trị có thể thay đổi dc"* ("O5 OK, but the value must be changeable"). The cap is the existing configuration key `trading.max_notional_per_order_usdt` (`src/config/app_config.json:19`). Bots, the planner and the slicing read its current value; none hard-codes 500. | No safety knob is loosened for the fast track, and the implied limit is stated up front instead of discovered at Start. A partial-slice failure is defined in §3.4. An exit of N × 500 USDT takes about N × `min_order_spacing` (5,000 USDT is about 2.5 s at 250 ms); the planner shows that figure. |
| D7 | **Trading publishes `TradingSwitchChangedEvent(venue, enabled, cause)` at the moment the switch changes (r1).** `cause` is ENABLED, DISABLED or EMERGENCY_STOP. For an Emergency Stop it is published at step 1, the disable, **before** the cancels and sells. | ✅ Accepted | 🤖 agent | Bots learn of a stop before their next submit. There is no window in which the bot misreads a switch-off refusal as a fault. |
| D8 | **The Spot cancel event carries the original id.** When `X` is CANCELED and `"C"` is present, the parser uses `"C"`. Proven red first, then on Testnet. | ✅ Accepted | 🤖 agent | A cancelled ladder order is recognised. If confirmed, the defect is filed as a `BUG-`; it affects the desks too. |
| D9 | **One serial worker per running bot (actor).** Events are copied off the websocket thread into the bot's queue, and only the worker submits, cancels and writes the store. **Refusals are classified (r1):** `TRADING_SWITCH_OFF` and `CONNECTION_NOT_READY` are `switch_off`, never `fault`. | ✅ Accepted | 🤖 agent | One writer for the ladder state. A switch-off during an Emergency Stop leads to HALTED, not ERROR. |
| D10 | **Fills are accumulated by the bot.** The event carries only this fill's quantity, so the executor keeps an executed quantity per order. The counter order is placed only on a full fill. | ✅ Accepted | 🤖 agent | Correct when Binance splits fills. The book is already updated when the bot sees the fill (D6), so the counter SELL is never refused for inventory. |
| D11 | **Stop loss and take profit are watched by the app** on `MarketTickEvent`. An exchange-side stop waits for `EPIC-026K`. | ✅ Accepted | 🤖 agent | A stop works only while the app runs. The UI says so, and closing the app warns (O4). |
| D12 | **A bot never places an order at app start.** On restart:<br>• a Running or Paused bot restores as RECOVERING;<br>• a Starting bot restores as HALTED **(r2)**: it may hold a half-sliced opening buy and part of a ladder, so it resumes only through D13;<br>• a Stopping bot restores as STOPPING;<br>• a Halted bot restores as HALTED.<br>When the user enables trading, every restored bot that is not DRAFT or STOPPED first **reclaims its lease** **(r2)**, because leases live in memory (T/application/trading_session_state.py:92). A RECOVERING bot then reconciles (§3.3) **(r1)**. | ✅ Accepted | 🤖 agent | Enabling trading stays the one human act that lets orders flow. A stop interrupted by a crash finishes; it is never reported as done. |
| D13 | **Any switch-off halts the venue's bots, and resuming a Halted bot always starts by cancelling every order carrying its tag (r1).** It then derives the inventory (D6) and proposes a new plan from the current price and that inventory, for the user to confirm (O2). | ✅ Accepted | 🤖 agent | Correct after both a disable (orders still resting) and an Emergency Stop (flat, partly flat or invested, §1.4). No ladder is ever laid over orphans. |
| D14 | **Grid backtest fill rule.** A resting order fills only when price trades **through** its level by at least one tick. Which levels a candle reached comes from 1-second klines. A level fills at most once per 1-second kline. **Every ladder fill pays the maker fee; the opening buy and stop-loss and take-profit exits pay the taker fee.** Every result names its rule. | ✅ Accepted | 🤖 agent | Conservative against the report's fill-on-touch. The planner's break-even uses the same fee model: `2 × maker` **(r1)**. |
| D15 | **One live candle chart, shared.** `ChartCoordinator` moves to `src/support/charting/live_chart/` behind a support-owned `CandleFeed` ABC with three operations: `load_history`, `sync(…)` and `start_stream`. The worker runner is injected **(r1)**. trading and bots adapt `IHistoricalKlines`, `IMarketDataSync` and `IMarketStream` to it. Horizontal lines come from a new `PriceLevelLayer` that leaves `chart_card.py` unchanged. | ✅ Accepted | 🤖 agent | Moves shared logic up instead of copying 229 lines. The desks keep their sync-then-read behaviour, so their tests run unmodified. |
| D16 | **One `GridOverlay` computation draws three surfaces:** the planner preview, the backtest result and the running bot. | ✅ Accepted | 🤖 agent | Backtest and live cannot draw differently (`strategy_overlay_coordinator.py:1-25`). |
| D17 | **ATR and Bollinger Bands** are pure functions over candle sequences in `src/support/indicators/`. | ✅ Accepted | 🤖 agent | They need high, low and close; `IIndicator.update(value)` takes one value. |
| D18 | **Buy-and-hold** is computed in `bots/domain`. | ✅ Accepted | 🤖 agent | No dependency on `backtesting`. |
| D19 | **The route is `bots`**, NAVIGATION item 18. | ✅ Accepted | 🤖 agent | `test_screen_wiring.py` changes in three places (029F). |
| D20 | **At most one Running bot during the fast track**, as a runtime check. `EPIC-029J` lifts it. | ✅ Accepted | 🤖 agent | "Many by design, one at a time first" (🟢). |

**What D6 consists of.**

- **The budget.** `OwnerBudget` holds `max_open_orders`, `max_exposure_quote`, `min_order_spacing`
  and an order-rate window (`max_orders`, `window`). O1 sets the global caps on what a budget may
  declare; they are checked against the venue's `ORDERS` rate limits, not only `REQUEST_WEIGHT`.
- **The owner book.** Trading keeps it for each budgeted owner: the owner's open orders, and its
  inventory. The inventory is the base it bought minus the base it sold, **net of base-asset fees**,
  together with its cost.
- **The book is updated inside trading's user-data path, before the event is published.** A fill
  is applied to the book by the venue's event-emission path, and only then published on the bus.
  So any subscriber, the bot included, sees a book that already contains that fill.
- **Seeding, per run (r2).** When a budget is registered, trading **derives** the inventory from
  exchange evidence: the executions of the owner's tagged orders **since the bot's current run
  started** (`run_started_at`, set on each `start` from DRAFT or STOPPED, and kept across HALTED,
  RECOVERING and STOPPING), minus their base-asset fees.
  - It uses order history with the exchange order id, plus trade history for the fees. `EPIC-029A`
    adds the order id to `OrderRecord`.
  - To bound the cost of history, trading may persist a checkpoint it computed itself.
  - The caller supplies only the owner id, the tag and `run_started_at`. **It never supplies the
    inventory.**
  - Base the user kept after a Stop belongs to the user. A new run does not count it.
- **Every sell of a bot's coins carries the bot's tag (r2).** This is what makes the tagged
  derivation complete.
  - Emergency Stop takes a snapshot of the owner books **before** its step-1 clear.
  - Its liquidation sells are split per budgeted owner: each owner's share, up to its inventory,
    goes out with that owner's tag. Only the surplus beyond every bot's inventory stays untagged
    (§1.4).
  - The same rule binds any later path that sells a bot's coins, such as `EPIC-029I`'s takeover.
- **Lifetime (r2).** Trading clears every budget and book on a disable or an Emergency Stop. The
  bot clears its own on entering STOPPED.
  - A bot holds a budget only after registering it.
  - It registers again, which re-derives the inventory, **before any order in any state**:
    reconciliation (§3.3), resume from HALTED (D13), a STOPPING retry, and ERROR → `stop`.
- **The checks.** For a budgeted owner's orders, trading does **not** apply
  `max_positions_per_symbol`, `min_order_interval` or `max_orders_per_session`. It enforces five
  checks instead, **whatever the order's `purpose`** **(r2)**. The budget branch runs before the
  `only_reduces` early return (T/domain/policies/trading_limit_policy.py:51-55), because Spot has no
  reduce-only and a Spot SELL marked CLOSE must still pass check 3. The five checks:
  1. open orders at or below `max_open_orders`;
  2. exposure at or below `max_exposure_quote`, where exposure is the open BUY quote plus the
     inventory at cost;
  3. open SELL quantity at or below the inventory;
  4. orders at least `min_order_spacing` apart;
  5. orders within the window at or below the rate cap.

  A sixth gate, **`OWNER_BUDGET_MISSING`** **(r2)**, refuses any order carrying a
  `client_order_tag` when no budget is registered for that tag. A bot can never fall back to the
  signal limits, which have no inventory check.

  The cap on notional per order (D21), the lease, the switch and the minimum notional still apply
  to every order.

## 3. The design behind D3, D6, D12, D13 and D21

### 3.1 Bot lifecycle (D3, D12, D13)

| From \ event | `edit` | `delete` | `start` | `ladder_ready` | `start_refused` | `pause` | `resume` | `stop` | `stop_confirmed` | `switch_off` | `reconcile_ok` | `reconcile_mismatch` | `fault` | `app_restart` |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| DRAFT | DRAFT | (removed) | STARTING | — | — | — | — | — | — | — | — | — | — | DRAFT |
| STARTING | — | — | — | RUNNING | HALTED | — | — | STOPPING | — | HALTED | — | — | ERROR | HALTED **(r2)** |
| RUNNING | — | — | — | — | — | PAUSED | — | STOPPING | — | HALTED | — | — | ERROR | RECOVERING |
| PAUSED | — | — | — | — | — | — | RUNNING | STOPPING | — | HALTED | — | — | ERROR | RECOVERING |
| RECOVERING | — | — | — | — | — | — | — | STOPPING | — | RECOVERING | prior (RUNNING or PAUSED) | HALTED | ERROR | RECOVERING |
| HALTED | — | — | — | — | — | — | STARTING (re-plan, D13) | STOPPING | — | HALTED | — | — | ERROR | HALTED |
| STOPPING | — | — | — | — | — | — | — | — | STOPPED | STOPPING (waits) | — | — | ERROR | STOPPING |
| STOPPED | DRAFT | (removed) | STARTING | — | — | — | — | — | — | — | — | — | — | STOPPED |
| ERROR | — | — | — | — | — | — | — | STOPPING | — | ERROR | — | — | — | ERROR |

The rules behind the table:

- **`stop_confirmed`** is raised only by a read that shows **zero open orders carrying the bot's
  tag**, after the base asset has been handled per O3.
  - While the switch is off, cancels are refused (§1.2), so STOPPING waits.
  - It retries when the switch comes back. It is never reported as STOPPED early.
- **The lease is released only on entering STOPPED (r2).** It is reclaimed on enable after a restart
  (D12). The bot clears its budget on entering STOPPED, and trading clears every budget on a disable
  or an Emergency Stop, so a bot re-registers before any order (D6).
- **STOPPING after a switch-off (r2)** re-registers (D6), cancels its tagged orders, then handles the
  base. **ERROR → `stop`** does the same.
- **`start_refused`** is a refusal after the opening buy. The bot cancels what it placed and halts
  with the reason, keeping its inventory accounted, so the user can resume (re-plan) or stop.
  Start's preconditions (the venue enabled, no REFUSED verdict, the lease, the budget) are checked
  by the start use case **before** the `start` transition. A refusal there leaves the state unchanged
  (DRAFT or STOPPED), with nothing to clean up.
- **`pause` while STARTING is not declared.** The UI disables it, and a call raises.
- **ERROR → `stop` → STOPPING** is the exit from ERROR. ERROR keeps the lease until then, so no
  manual order can hit the bot's symbol while its state is unknown. After a restart the lease comes
  back on enable (D12) **(r2)**.

### 3.2 Grid level lifecycle (D3, D10)

| From \ event | `place` | `accepted_or_resting` | `partial_fill` | `full_fill` | `ended` | `adopt` |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| EMPTY | PLACING | — | — | — | — | RESTING |
| PLACING | — | RESTING | PARTIAL | FILLED | EMPTY (+1 failure) | — |
| RESTING | — | — | PARTIAL | FILLED | EMPTY (+1 failure) | — |
| PARTIAL | — | — | PARTIAL | FILLED | EMPTY (keeps executed qty as inventory) | — |
| FILLED | — | — | — | — | — | — |

- **FILLED** emits the counter order one level away, and the level returns to EMPTY. **Two
  `ended` events at one level within a minute** halt the bot with `LEVEL_KEEPS_ENDING`.
- **At start, the level nearest the last price** (within half a step) stays EMPTY, so no order is
  marketable at the taker fee. Levels strictly below the price are BUY and levels strictly above
  are SELL. `max_open_orders = grid_count + 1` is the number of levels: an upper bound with one
  level of slack.

### 3.3 Reconciliation (D12, D13), in this order

1. **Claim the lease** under the bot's id.
2. **Register the budget.** Trading derives the inventory from exchange evidence (D6) and seeds
   the book with the tagged open orders.
3. **Read the open orders carrying the bot's tag.**
4. **Apply fills first.** A saved RESTING or PARTIAL order missing from the exchange is looked up
   in order history, and its fill is applied.
5. **Then adopt.** A tagged order unknown to the saved state is adopted at its level by price. A
   level holding an adopted order is never re-placed. Two tagged orders at one level halt the bot
   with `DUPLICATE_LEVEL_ORDER`.
6. **Check the inventory.**
   - The saved inventory must equal the derived inventory to within one step size; otherwise the
     bot halts with `INVENTORY_MISMATCH`.
   - The account's holding must be **at least** the derived inventory; otherwise the bot halts
     with `HOLDING_BELOW_INVENTORY`.
   - It is never an equality with the account's holding, which includes the user's own coins.
7. **Persist,** then transition: `reconcile_ok` or `reconcile_mismatch`.

### 3.4 Sliced market orders: the opening buy and every exit (D21)

- **Slicing.** The opening quote is split into ⌈quote / cap⌉ market BUY slices, each at most the
  cap, spaced by `min_order_spacing`.
- **A slice refused or failed** stops the opening. Nothing of the ladder has been placed yet. The
  bot raises `start_refused`, which leads to HALTED with the acquired inventory derived.
- **Resuming** re-plans with that inventory. The SELL side is sized to what was actually bought.
- **Exits (r2).** A stop-loss or take-profit exit, and Stop with *sell base*, sell the inventory in
  slices at or below the cap, spaced by `min_order_spacing`.
  - A refused or failed exit slice halts the bot, naming the unsold remainder; nothing is retried
    silently.
  - Every exit slice carries the bot's tag and passes check 3.

## 4. Alternatives considered

- **Raise the global session limits instead of D6.** It loses because it loosens manual and
  strategy trading at the same time and bounds no single bot.
- **Let the bot bypass trading's limits.** It loses because trading would stop being the one place
  every order is bounded (D1).
- **Seed the owner book from the bot's store (first draft).** Rejected in review round 1. The
  account's holding includes the user's coins, so any store error could unlock selling them.
  Exchange evidence filtered by tag is the only trustworthy source (D6).
- **An Emergency Stop checkpoint instead of tagged liquidation (r2).** Emergency Stop would write a
  trading-computed debit per owner. It is viable, and D6 allows checkpoints. It lost because tagging
  keeps the inventory provable from exchange evidence alone.
- **One HALTED for both causes, without cancelling (first draft).** Rejected in review round 1. A
  disable leaves orders resting, so a re-plan without cancelling first laid a second ladder over
  them (D13).
- **Raise `max_notional_per_order` for bots, or a per-owner cap in the budget.** It is viable, and
  offered to the user as O5's alternative. The recommendation keeps the existing cap and slices
  the opening buy (D21), so that no safety knob is loosened on the fast track.
- **Bot-generated client order ids.** It loses because id format and uniqueness belong to trading.
  A tag is enough.
- **Binance's native Spot grid.** It loses because it skips the app's gates, the fake exchange and
  the Testnet tier, and was never checked against the API (`PRO-006` §2.3).
- **Copy `ChartCoordinator` into `bots/ui`.** It loses because 229 lines would drift (P6).
- **A SQLite table for bots.** It loses because one file per bot is enough at this scale; it can be
  revisited at `EPIC-029J`.
- **Exchange-side stops now.** These wait for `EPIC-026K` (D11).

## 5. Questions, answered by the user on 2026-10-03

Every recommendation below was accepted. O1's caps and O5's per-order cap are configuration values the user can change.


| # | Question | Recommendation | Blocks | Asked on |
| :-- | :--- | :--- | :--- | :--- |
| O1 | **Global caps on what an owner budget may declare.** These are new `app_config.json` keys: `trading.bot_limits.max_open_orders`, `.min_order_spacing_ms`, `.max_orders_per_minute`. | 100 open orders; 250 ms; 60 orders per minute. Checked in `EPIC-029A` against the venue's `ORDERS` rate limits. | `EPIC-029A` | 2026-10-03 |
| O2 | **Resuming a Halted bot:** cancel its tagged orders, re-plan from the current price and derived inventory, and confirm; or rebuild the old ladder silently? | Cancel, re-plan, confirm (D13) | `EPIC-029E` | 2026-10-03 |
| O3 | **Stop dialog default for the base asset:** keep it, or sell it at market? | Ask each time, with *keep* preselected | `EPIC-029E` | 2026-10-03 |
| O4 | **Closing the app while a bot is Running:** warn that its orders stay on the exchange and its stop loss is not watched? | Warn, with Cancel | `EPIC-029F` | 2026-10-03 |
| O5 | **Per-order notional for bots** (r1): keep today's `max_notional_per_order` (500) and slice the opening buy, or give bots their own cap? | Keep 500 and slice (D21). Capital per level is then at most 500. | `EPIC-029A`, `029C` | 2026-10-03 |

## 6. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D5, D6, D7, D8, D21 (the trading half) | [`EPIC-029A`](incomplete/EPIC-029A_trading_seams_for_bots.md) | Not started | Not yet verified |
| D1, D2, D3 (bot lifecycle), D4, D20 | [`EPIC-029B`](incomplete/EPIC-029B_bots_module_entity_and_store.md) | Not started | Not yet verified |
| D17, D21 (the planner refusal), the planner | [`EPIC-029C`](incomplete/EPIC-029C_grid_planner.md) | Not started | Not yet verified |
| D14, D18 | [`EPIC-029D`](incomplete/EPIC-029D_grid_backtest.md) | Not started | Not yet verified |
| D3 (level lifecycle), D9–D13, §3.3, §3.4 | [`EPIC-029E`](incomplete/EPIC-029E_live_grid_executor.md) | Not started | Not yet verified |
| D19 | [`EPIC-029F`](incomplete/EPIC-029F_bots_tab.md) | Not started | Not yet verified |
| D15, D16 | [`EPIC-029G`](incomplete/EPIC-029G_bot_chart.md) | Not started | Not yet verified |
