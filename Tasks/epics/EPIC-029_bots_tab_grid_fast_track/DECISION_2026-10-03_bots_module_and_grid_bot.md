# ADR — Bots get their own module, entity and lifecycle, and the first one is a Grid bot on Spot that trading executes under an owner budget

**Epic:** [EPIC-029](README.md)
**Date:** 2026-10-03
**Status:** Proposed
**Decided by:** Pending. The user accepted [`PRO-006`](../../proposal/PRO-006.md) on 2026-10-03
(*"Oki, duyệt, nhớ design đúng nha, ko lazy design"*, "OK, approved; get the design right, no lazy
design"). That acceptance covers the direction and the phase order. The decisions below are the
design that follows from it. Each one is 🤖 proposed by the agent under `ONBOARDING.md` §7, and
waits for an independent review and then the user. D6 and the open questions O1–O4 need the user
specifically: D6 changes a safety gate, and O1 adds configuration.

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

| Need of a Grid | What exists | Where |
| :--- | :--- | :--- |
| Place a LIMIT GTC order on Spot | Yes, through the venue's `IOrderSubmission.submit()`, obtained from `IVenueTradingPorts.get(venue)` | T/contracts/i_order_submission.py:243-306; T/contracts/venue_trading_ports.py:49-59 |
| Market BUY by quote quantity (the opening purchase) | Yes, only for a market BUY | T/adapters/binance/spot/spot_order_payload_mapper.py:98-104 |
| Choose its own client order id, or a prefix | **No.** Always `SEW-` + 12 hex, generated inside trading. The caller learns it only from the result. | T/contracts/client_order_id.py:28-40; T/application/orders/preview_order/handler.py:102 |
| Name the order's owner | Yes, `OrderRequest.owner_id` | T/contracts/order_request.py:56-87 |
| Cancel one order | Yes: `IOrderSubmission.cancel(symbol, client_order_id)`, gated only by the switch and the connection | T/contracts/i_order_submission.py:299; T/application/orders/cancel_order/handler.py:96-105 |
| Read its open orders | Account-wide only, with no symbol filter. An `Order` has no executed quantity. | T/contracts/i_account_activity.py:52; T/contracts/order.py:51-71 |
| Learn of fills | `OrderFilledEvent`: `order`, `fill_price`, `fill_quantity` (this fill only), `fee_amount`, `fee_asset`, `venue`. Published on the websocket thread. | T/contracts/events/order_filled_event.py:41-56; T/adapters/binance/spot/spot_user_data_stream.py:229-235 |
| Learn of cancels and expiries | `OrderEndedEvent`. But the Spot parser reads only `"c"`. On a cancel, Binance documents `"c"` as the cancel request's id and `"C"` as the original order's id, so the event may name the wrong order (❓ verified against the code, **not** against Binance; `EPIC-029A` proves it). | T/adapters/binance/spot/spot_user_data_event_parser.py:70 |
| Learn that an order was accepted | **No event.** `place_order` returns the request unchanged, with status NEW. `submit()` can raise. | T/adapters/binance/spot/spot_trading_client.py:97-109 |
| Claim a symbol under its own owner | Yes: `ITradingSession.claim_symbol(symbol, owner_id)`. One symbol per owner. The holder cannot be queried. | T/contracts/i_trading_session.py:134-153 |
| Query the symbol's filters and fees | Yes: `order_entry_terms.terms_for(symbol)` returns `tick_size`, `step_size`, `min_notional` and `CommissionRate(maker, taker)` | T/contracts/i_order_entry_terms.py:117; T/contracts/commission_rate.py:44-46 |
| Learn that trading was enabled, disabled or Emergency-Stopped | **No event.** Only `ITradingSession.snapshot().enabled`, by polling. The user data stream runs only while trading is enabled. | T/contracts/i_trading_session.py:112; T/application/session/enable_trading/handler.py:134 |

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

### 1.4 Emergency Stop on Spot liquidates a bot's inventory (✅)

- Emergency Stop cancels every open order on the account. It then sells, at market, each asset's
  holding above the baseline captured at enable
  (T/application/session/emergency_stop/handler.py:115, 224-306;
  T/application/session/enable_trading/handler.py:108-117).
- A Grid's opening purchase and its filled buys are all above that baseline, so they are sold.
- It publishes nothing. Its result goes only to the caller (T/contracts/emergency_stop_result.py:49-54).

### 1.5 Charting and data (✅)

- **`ChartCard` is a frozen god file.** It is 881 lines and baselined
  (`tests/unit/architecture/baseline_god_files.json`), so it cannot grow. It draws:
  - candles;
  - indicator lines (`add_overlay_indicator`, `update_indicator_data`);
  - **vertical** time spans (`set_script_regions`);
  - markers (`set_script_markers`, `src/support/charting/chart_card/chart_card.py:705-760`).

  It has **no horizontal price lines**: the only one is its internal last-price line.
- **The desk's live chart cannot be reused as it is.** `ChartCoordinator` (229 lines) loads
  history through `IHistoricalKlines` and live candles through `IMarketStream`. It depends only on
  market_data contracts and `support/charting`, but it lives in
  `trading/ui/desk/desk_screen/chart_coordinator.py`, where another module cannot import it.
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

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **A new `bots` module** owns the Bot entity, the store, the lifecycle and the Bots screen. It depends only on `trading` and `market_data` contracts. `trading` stays the only module that sends orders. | 🔵 Proposed | 🤖 agent | One more module. The guards in §1.6 apply, the vocabulary's "exactly four modules" line changes, and HLD 02/03 gain a row. |
| D2 | **Bot** is a persisted aggregate: `BotId`, name, `BotKind`, venue, symbol, kind config and lifecycle state. **`BotKind` is the seam.** It is an ABC whose implementations supply the parameter schema and verdicts, the executor factory and the chart overlay. Only `GridKind` is built. | 🔵 Proposed | 🤖 agent | Signal, DCA and Futures Grid later plug in without touching the shell. Architecture rule §7.2.1: build the seam with its first case, list the extension cases in its docstring, and do not build them. |
| D3 | **Lifecycle FSM** in `bots/domain/bot_lifecycle_fsm_matrix.py`, Qt-free (§3.1). | 🔵 Proposed | 🤖 agent | One declared transition table. Everything that changes a bot's state goes through it, and an undeclared transition raises. |
| D4 | **Store**: one JSON file per bot under `state/bots/<bot_id>.json`, schema-versioned and written atomically (tmp + `replace`, the precedent in §1.6). The file holds the definition **and** the runtime ladder state. It is written after every runtime change. | 🔵 Proposed | 🤖 agent | Survives restarts. One bot is one file, which is easy to inspect and to delete. No database migration. `state/` is already gitignored. |
| D5 | **Client order ids carry a bot tag.** `OrderRequest` gains an optional `client_order_tag`. Trading generates `SEW-{tag}-{hex10}`, where the tag is 6 characters of `[a-z0-9]`, giving 21 of Binance's 36 characters. An untagged order keeps `SEW-{hex12}`. | 🔵 Proposed | 🤖 agent | A bot recognises its own orders in an account-wide open-orders read, after a crash or restart and before any local state exists. Trading still owns id generation and uniqueness. |
| D6 | **Owner budget instead of the signal limits, for orders whose owner registered one.** A bot registers an `OwnerBudget(max_open_orders, max_exposure_quote, min_order_spacing)` with the venue's trading session before it starts. Trading then keeps an **owner book** from that owner's own submits and fills: open orders, and the owner's inventory (the base it bought minus the base it sold, with its cost). For that owner's orders, trading does **not** apply `max_positions_per_symbol`, `min_order_interval` or `max_orders_per_session`. It enforces four checks instead, listed below this table. | 🔵 Proposed, **needs the user** (it changes a safety gate) | Pending | Ladders become possible while trading still bounds every bot. A bot can never sell holdings that were the user's before it started; this is the class of defect fixed in PR #284. A bug in an executor cannot exceed the budget it declared, and O1's global caps bound what a budget may declare. Manual and strategy orders are unchanged. |
| D7 | **Trading publishes `TradingSwitchChangedEvent(venue, enabled, cause)`**, where `cause` is ENABLED, DISABLED or EMERGENCY_STOP, from the enable, disable and Emergency Stop handlers. | 🔵 Proposed | 🤖 agent | Bots learn of a stop without polling. Desks can use it later. Additive. |
| D8 | **The Spot cancel event carries the original id.** When `X` is CANCELED and `"C"` is present, the parser uses `"C"`. This is proven red first against a recorded executionReport, then verified on Testnet. | 🔵 Proposed | 🤖 agent | A cancelled ladder order is recognised. If the defect is confirmed it is filed as a `BUG-` and fixed under `fix-bug-rule.md`; it affects the desks' open-orders panel too. |
| D9 | **One serial worker per running bot (actor).** Fill, end, tick and switch events are copied off the websocket thread into the bot's queue. Only the worker submits, cancels and writes the store. | 🔵 Proposed | 🤖 agent | No lock is held across a network call, and the ladder's state has exactly one writer. The pattern is the Actor model: a single-consumer queue per aggregate. |
| D10 | **Fills are accumulated by the bot.** The event carries only this fill's quantity, so the executor keeps an executed quantity per order. The counter order is placed only when the order is fully filled. A partial fill shows as a partially filled level. | 🔵 Proposed | 🤖 agent | Correct when Binance splits fills. The level states are listed in §3.2. |
| D11 | **Stop loss and take profit are watched by the app** on `MarketTickEvent`. When one triggers, the bot cancels its ladder and sells its base at market. An exchange-side stop waits for `EPIC-026K`. | 🔵 Proposed | 🤖 agent | A stop only works while the app runs. The UI says so, and closing the app warns while a bot is Running (O4). |
| D12 | **A bot never places an order at app start.** A bot saved as Running is restored as **Paused (recovering)**. When the user enables trading on its venue, the bot reconciles (§3.3). If reconciliation succeeds it resumes; if not it is Halted with the reason. | 🔵 Proposed | 🤖 agent | Enabling trading stays the one explicit human act that lets orders flow, as it is today. |
| D13 | **An Emergency Stop halts the venue's bots.** Their orders are already cancelled and their inventory already sold (§1.4). Resuming a Halted bot re-plans from the current price and holdings, and needs the user's confirmation (O2). | 🔵 Proposed | 🤖 agent | Matches what Emergency Stop does to the account. No ladder resumes on a stale plan. |
| D14 | **Grid backtest fill rule.** A resting order fills only when price trades **through** its level by at least one tick. Which levels a candle reached comes from 1-second klines. Within one 1-second kline, a level fills at most once (no round trip inside it). Maker fee applies to ladder fills; taker fee to the opening buy and to stop loss and take profit exits. Every result names its rule. | 🔵 Proposed | 🤖 agent | Conservative against the report's fill-on-touch. A result cannot claim cycles that one candle hides. |
| D15 | **One live candle chart, shared.** `ChartCoordinator` moves from `trading/ui/desk/desk_screen/` to `src/support/charting/live_chart/`, behind a support-owned `CandleFeed` ABC. trading and bots each adapt `IHistoricalKlines` and `IMarketStream` to it. Horizontal price lines come from a new `PriceLevelLayer` that attaches to `ChartCard`'s plot without growing `chart_card.py`. | 🔵 Proposed | 🤖 agent | Moves shared logic up (`fix-bug-rule.md` §1, P6) instead of copying 229 lines. The desks' chart tests guard the move. The frozen `ChartCard` stays frozen. |
| D16 | **One `GridOverlay` computation draws three surfaces:** the planner preview, the backtest result and the running bot. | 🔵 Proposed | 🤖 agent | The rule `strategy_overlay_coordinator.py:1-25` states for strategies: backtest and live cannot draw differently. |
| D17 | **ATR and Bollinger Bands** are pure functions over candle sequences in `src/support/indicators/`, not `IIndicator` implementations. | 🔵 Proposed | 🤖 agent | They need high, low and close. `IIndicator.update(value)` takes one value. |
| D18 | **Buy-and-hold** is computed in `bots/domain` for a Grid backtest. | 🔵 Proposed | 🤖 agent | No dependency on `backtesting`, which publishes no such thing. |
| D19 | **The route is `bots`**, NAVIGATION item 18, after Spot (17). | 🔵 Proposed | 🤖 agent | The route map pinned in `test_screen_wiring.py` gains one row. |
| D20 | **At most one Running bot during the fast track.** This is a runtime check in `bots/application`, not a structural limit. `EPIC-029J` lifts it. | 🔵 Proposed | 🤖 agent | "Many by design, one at a time first" (🟢). |

**D6's four checks.** For an owner with a registered budget, trading refuses an order unless:

1. the owner's open orders stay at or below `max_open_orders`;
2. exposure stays at or below `max_exposure_quote`, where exposure is the open BUY orders' quote
   plus the inventory at cost;
3. the owner's open SELL quantity stays at or below the owner's inventory;
4. orders are at least `min_order_spacing` apart.

Every order, budgeted or not, still passes `max_notional_per_order`, the lease, the switch and the
minimum notional.

**A budget lives only as long as the session.** Budgets and owner books belong to the venue's
trading session, like `known_open_symbols`, and are cleared when the session is disabled or
Emergency-Stopped. When a bot comes back after reconciliation (§3.3), it registers again and seeds
its book from what the exchange reports:

- its tagged open orders;
- its inventory, capped at the account's actual holding of the asset.

So a stale book never outlives the session it was built in.

## 3. The design behind D3, D10 and D12

### 3.1 Bot lifecycle (D3)

| From \ event | `start` | `pause` | `resume` | `stop` | `ladder_ready` | `stop_done` | `switch_off` / `emergency_stop` | `fault` | `app_restart` |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| DRAFT | STARTING | — | — | — | — | — | — | — | DRAFT |
| STARTING | — | — | — | STOPPING | RUNNING | — | HALTED | ERROR | PAUSED_RECOVERING |
| RUNNING | — | PAUSED | — | STOPPING | — | — | HALTED | ERROR | PAUSED_RECOVERING |
| PAUSED | — | — | RUNNING | STOPPING | — | — | HALTED | ERROR | PAUSED_RECOVERING |
| PAUSED_RECOVERING | — | — | RUNNING (after reconcile) | STOPPING | — | — | stays | HALTED | PAUSED_RECOVERING |
| STOPPING | — | — | — | — | — | STOPPED | STOPPED | ERROR | STOPPED |
| HALTED | — | — | STARTING (after re-plan confirm) | STOPPED | — | — | stays | — | HALTED |
| STOPPED / ERROR | STARTING (Stopped only) | — | — | — | — | — | — | — | same |

The meaning of each state:

- **PAUSED:** resting orders stay on the exchange. Fills are still recorded, but no counter order
  is placed.
- **STOPPING:** the bot cancels every order it owns. Then, by the user's choice in the stop
  dialog, it keeps the base or sells it at market.
- **ERROR:** an executor fault the bot could not classify. It keeps the lease. A person inspects
  the bot and stops it.

### 3.2 Grid level states (D10)

- **EMPTY → RESTING(order id) → PARTIAL(executed) → FILLED.** FILLED triggers the counter order,
  one level away on the other side, and the level becomes EMPTY again.
- **An order that ends without filling** returns its level to EMPTY. While the bot is Running, the
  level is re-placed once. A second failure halts the bot with the reason.
- **A partial order that ends** keeps its executed quantity as inventory, and the level returns to
  EMPTY.

### 3.3 Reconciliation (D12, D13)

The bot runs these steps on its own worker when trading is enabled:

1. Read the account's open orders and keep those whose id carries the bot's tag (D5).
2. Compare them with the saved levels:
   - a saved RESTING order missing from the exchange is looked up in order history; if it filled,
     its fill is applied;
   - an exchange order unknown to the saved state is adopted at its level by price;
   - anything else halts the bot with a named mismatch.
3. Read the base holding and compare it with the saved inventory. A difference beyond one step
   size halts the bot.
4. Persist the result, then resume.

## 4. Alternatives considered

- **Raise the global session limits instead of D6.** One `app_config.json` edit would let ladders
  through. It loses because it loosens manual and strategy trading at the same time and bounds no
  single bot. A mistyped order count would apply account-wide.
- **Let the bot bypass trading's limits entirely.** It loses because trading would stop being the
  one place every order is bounded (D1).
- **Bot-generated client order ids.** The caller would pass a full id. It loses because id
  uniqueness and format belong to trading (T/contracts/client_order_id.py). A tag gives the bot
  what it needs, which is recognising its own orders.
- **Binance's native Spot grid via API.** It loses because it skips the app's safety gates, the
  fake exchange and the Testnet tier. It was also never checked against the current API
  (`PRO-006` §2.3).
- **Copy `ChartCoordinator` into `bots/ui`.** It loses because 229 duplicated lines would drift
  (P6). Publishing it from `market_data` as a port was also considered: it would work, but it would
  put a ChartCard-shaped API in a data module's contracts. D15 keeps chart concerns in
  `support/charting`.
- **A SQLite table for bots.** It loses because one human-readable file per bot is enough for
  dozens of bots and needs no migration tooling. It can be revisited at `EPIC-029J` if bots number
  in the hundreds.
- **Exchange-side stops now.** These would be Spot `STOP_LOSS_LIMIT` or OCO orders. They wait for
  `EPIC-026K`'s protective-order work, so as not to fork that design. D11 is explicit about the
  cost: the stop works only while the app runs.

## 5. Open questions

| # | Question | Recommendation | Blocks | Asked on |
| :-- | :--- | :--- | :--- | :--- |
| O1 | **Global caps on what an owner budget may declare.** These are new `app_config.json` keys: `trading.bot_limits.max_open_orders` and `trading.bot_limits.min_order_spacing_ms`. | `max_open_orders` 100 (a Grid needs N+1); `min_order_spacing_ms` 250, which is 4 orders per second. That this is inside the venue's order rate limit is checked against `exchangeInfo.rateLimits` in `EPIC-029A`, not assumed. | `EPIC-029A` | 2026-10-03 |
| O2 | **Resuming a Halted bot.** Re-plan from the current price and holdings and show it for confirmation, or rebuild the old ladder silently? | Re-plan and confirm | `EPIC-029E` | 2026-10-03 |
| O3 | **Stop dialog default for the base asset:** keep it, or sell it at market? | Ask each time, with *keep* preselected | `EPIC-029E` | 2026-10-03 |
| O4 | **Closing the app while a bot is Running:** warn that its resting orders stay on the exchange and that its stop loss is not watched? | Warn, with Cancel | `EPIC-029F` | 2026-10-03 |

## 6. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D5, D6, D7, D8 | [`EPIC-029A`](incomplete/EPIC-029A_trading_seams_for_bots.md) | Not started | Not yet verified |
| D1, D2, D3, D4, D20 | [`EPIC-029B`](incomplete/EPIC-029B_bots_module_entity_and_store.md) | Not started | Not yet verified |
| D17 and the planner | [`EPIC-029C`](incomplete/EPIC-029C_grid_planner.md) | Not started | Not yet verified |
| D14, D18 | [`EPIC-029D`](incomplete/EPIC-029D_grid_backtest.md) | Not started | Not yet verified |
| D9, D10, D11, D12, D13 | [`EPIC-029E`](incomplete/EPIC-029E_live_grid_executor.md) | Not started | Not yet verified |
| D19 | [`EPIC-029F`](incomplete/EPIC-029F_bots_tab.md) | Not started | Not yet verified |
| D15, D16 | [`EPIC-029G`](incomplete/EPIC-029G_bot_chart.md) | Not started | Not yet verified |
