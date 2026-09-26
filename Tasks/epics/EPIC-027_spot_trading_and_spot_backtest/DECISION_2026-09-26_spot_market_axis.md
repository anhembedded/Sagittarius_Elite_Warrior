# ADR — Spot becomes a second market type, added as an explicit axis beside Futures

**Epic:** [EPIC-027](README.md)
**Date:** 2026-09-26
**Status:** Proposed
**Decided by:** Pending — the user decides D1–D9 and answers O1–O6. The user asked on 2026-09-26:
*"đánh giá xem giờ tui muốn giao dịch spot và back test theo spot thì app này cần những gì, lên
plan và epic"* ("assess what this app needs now that I want to trade spot and backtest on spot;
make a plan and an epic").
**Supersedes / superseded by:** Revisits §1 of
[`EPIC-021`'s ADR](../EPIC-021_ket_noi_binance_futures_testnet/DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md)
("USD-M Futures Testnet, not Spot Testnet"). That decision stays in force for Futures; this record
adds Spot next to it and does not replace it.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context

The app was built for Binance USDⓈ-M Futures on purpose. `EPIC-021` chose Futures because Spot
cannot short, and the backtest already modeled shorts. `EPIC-026` lists "Spot and COIN-M" as out
of scope. The user now wants both Spot backtests and live Spot trading. The code tree was measured
on 2026-09-26 (merged `master-warrior`, `ee7105f8`).

**The backtest engine already has an implicit Spot mode.** ✅
- A 1× LONG position is valued and settled with spot arithmetic: `quantity × price`, proceeds back to
  cash (`src/modules/backtesting/domain/policies/margin_risk_policy.py:160,182`).
- A 1× LONG has no liquidation price (`margin_risk_policy.py:103`).
- `SignalAction.BUY`/`SELL` already mean "open long"/"close long". `SHORT`/`COVER` are separate facts
  (`src/modules/strategy/contracts/signal_action.py`).
- The default 0.1 % commission equals Binance Spot's base rate. Charging it in quote currency gives
  the same numbers as Spot charging it in the received asset.

What the engine does not have:
- a market-type switch;
- a way to refuse shorts;
- exchange-filter rounding (step size, minimum notional, tick size). Quantities are unrounded floats.

**The live trading path is Futures-only.** ✅
- `ITradingSessionClient` lists only `futures_*` methods
  (`src/support/binance_gateway/contracts/i_trading_session_factory.py:128-157`).
- `TradingVenue` has exactly `DISABLED` and `FUTURES_TESTNET` (`trading_venue.py:14-15`).
- Six call sites construct `FuturesTradingClient(...)` directly and bypass the DI binding: `execute_order/handler.py:159`,
  `cancel_order/handler.py:80`, `enable_trading/handler.py:113`, `emergency_stop/handler.py:118`,
  `get_open_positions/handler.py:60`, `futures_user_data_stream.py:233`.
- The domain speaks in signed positions with `reduce_only`, mark price, leverage and liquidation
  price (`contracts/live_position.py`, `contracts/order.py:60`).
- Spot has none of these. It has per-asset balances instead.

**A market-type enum already exists and nothing uses it.** ✅ `MarketType {SPOT, FUTURES_USD_M,
FUTURES_COIN_M}` (`src/domain/value_objects/market_type.py:10`). Its only consumer is an orphaned
`MarketPickerDialog` (`src/presentation/ui/components/market_picker/catalogue.py:20`). The Dev Board's
"Market: Spot/Futures" combo is inert: it is only ever enabled or disabled
(`dev_board_widgets/system_controls_card.py:140-145`), and
`tests/integration/presentation/ui/test_dev_board_known_gaps.py:104-116` pins that it does nothing.

**A truth finding this epic must close.** ✅ Stored candles do not record which market they came
from. The primary key is `(symbol, interval, open_time)`
(`src/modules/market_data/adapters/persistence/models.py:11-13`). The default market-data venue
`MAINNET_PUBLIC` downloads **Spot** klines
(`src/support/binance_gateway/contracts/binance_endpoints.py:52`). Mainnet Futures klines are never
downloaded.

So every leveraged, short-capable "Futures" backtest on the default venue today runs on **Spot
prices**. The settings label reads only "Mainnet — real, public prices". Switching the venue does
not partition the data, so candles from two markets can overwrite each other in one shard. The
difference between the two price series (the basis) is usually small, but it is a fact the screen
never states — `domain-truth-rule.md`.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **Market type is an explicit axis.** `MarketType` moves to the shared kernel published language (`src/core/vo/`) and keeps its three members. Scope is `SPOT` + `FUTURES_USD_M`; `FUTURES_COIN_M` stays unused. | 🔵 Proposed | Pending | One vocabulary for data, backtest and trading. The orphaned enum gets consumers. COIN-M is still unsupported, and that is stated. |
| D2 | **Stored candles are keyed by market.** One shard per (market, symbol). A sync asks for a market explicitly. Mainnet Spot klines come from `/api/v3`, mainnet Futures klines from `/fapi`. | 🔵 Proposed | Pending | Fixes the truth finding above: a Futures backtest can run on Futures prices. Costs a data migration (O3) and a second download for users who want both markets. |
| D3 | **Spot in the backtest means long-only, 1× and no liquidation.** A `market_type` field on `BrokerSimulationConfig` defaults to `FUTURES_USD_M`, so existing runs are byte-for-byte unchanged (`pitfalls/source.md` #1, #2). When it is `SPOT`, validation forces leverage to 1. | 🔵 Proposed | Pending | Reuses the existing 1× LONG arithmetic; no new valuation formula. |
| D4 | **In Spot, SHORT/COVER signals are dropped, counted and reported, never remapped.** A SHORT is not turned into a SELL. The result carries "N short signals ignored (spot)". | 🔵 Proposed | Pending | Keeps `domain-truth-rule.md` F2: an exit and a short entry are different facts. A short-heavy strategy shows honestly how little of it survives on Spot. |
| D5 | **Exchange filters apply to every simulated fill, in both markets.** Quantity is floored to the step size. An order below the minimum notional is rejected and counted. Price uses the tick size from metadata. Spot metadata already exists (`market_data/adapters/binance/market_metadata_parser.py`). | 🔵 Proposed | Pending | Backtests stop trading quantities the exchange would refuse. This slightly changes Futures results too, so the default is explicit: the filters are on, and they are recorded in the report. |
| D6 | **Live Spot is a second adapter set behind the same ports.** It gets its own client, account reader, user data stream and metadata provider. First, the six direct `FuturesTradingClient(...)` constructions go through one venue-selected factory. That refactor changes no behavior and goes in its own PR. | 🔵 Proposed | Pending | The refactor also serves `EPIC-026P`, since mainnet Futures needs the same factory parameter. Spot then plugs in without editing the handlers again. |
| D7 | **A Spot "position" is a holding.** It is the base-asset balance (free + locked) above a dust threshold. The average entry price is not given by the Spot API (O6). Equity is the quote balance plus holdings × last price. | 🔵 Proposed | Pending | The UI never invents a mark price, leverage or liquidation price for Spot. It shows balances. |
| D8 | **Live Spot starts on Spot Testnet only.** A new member `TradingVenue.SPOT_TESTNET` (`testnet.binance.vision`) gets its own credential names (`BINANCE_SPOT_TESTNET_API_KEY/_SECRET`), the same way `EPIC-021B` names Futures keys. Spot mainnet follows the same gates as `EPIC-026`, not a separate road. | 🔵 Proposed | Pending | Consistent with `EPIC-021` ADR §3: a venue that does not exist in the enum cannot be switched on by a config edit. |
| D9 | **Phase 1 supports only USDT-quoted pairs for Spot.** Arming or ordering a non-USDT pair is refused with a stated reason. | 🔵 Proposed | Pending | Trading limits and sizing are already in USDT (`config_keys.py:91`). Multi-quote support is deferred and stated (O4). |

## 3. Alternatives considered

- **Treat Spot as "Futures at 1× without shorts" in the live path, too.** Rejected. The Spot API has no
  positions, no `reduceOnly` and no `positionSide`, and a different user data stream (`executionReport`,
  `outboundAccountPosition`). Pretending otherwise would need an adapter that invents fields. This is
  the `BUG-026`/`CS-001` class: a double shaped by the caller, not by the real interface.
- **Map SHORT to "sell to flat" on Spot.** Rejected. It changes what a strategy means without saying so,
  and SELL would carry two facts (`domain-truth-rule.md` F2).
- **Split `TradingVenue` into environment × market (two enums).** Deferred, not rejected. With four
  real combinations (Futures/Spot × Testnet/Mainnet) a closed enum is still readable. Each member
  maps to exactly one session factory and one credential pair, which is the property
  `EPIC-021` ADR §3 relies on. Revisit if COIN-M ever enters scope.
- **Keep one shard per symbol and add a `market` column to the primary key.** Viable. Per-market shards
  are proposed because the existing export/import (`BOT-112D`), gap scan and vacuum all work per shard.
  A shard-level key keeps them unchanged. The task records the final choice.

## 4. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Order of work: **Spot backtest first** (Phase 1, no keys needed, most value soonest — recommended) or live Spot first? | Phase order | 2026-09-26 |
| O2 | Live arming of a strategy that can emit SHORT on a Spot venue: **refuse to arm** (recommended — a live account must not quietly skip half a strategy), or allow it with shorts dropped, the way the backtest does (D4)? | `EPIC-027N` | 2026-09-26 |
| O3 | Candles already stored have no market tag. **Tag them as Spot** (recommended: the default venue has always downloaded Spot klines), or mark them "unknown" until re-synced? Candles synced under `FUTURES_TESTNET` cannot be told apart after the fact. | `EPIC-027A` | 2026-09-26 |
| O4 | Is USDT-quoted only acceptable for the first release (D9)? | `EPIC-027N` | 2026-09-26 |
| O5 | Spot mainnet: through `EPIC-026`'s stages (journal, breaker, soak) like Futures (recommended), or earlier? Which market reaches real money first — Futures or Spot? | Out-of-scope boundary | 2026-09-26 |
| O6 | Where the Spot average entry price comes from: `GET /api/v3/myTrades` (recommended for Phase 3), or the app's own fill journal (`EPIC-026G`, not built yet)? | `EPIC-027H` | 2026-09-26 |

## 5. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [`EPIC-027A`](incomplete/EPIC-027A_market_aware_kline_storage_and_download.md) | Not started | Not yet verified |
| D2 | [`EPIC-027A`](incomplete/EPIC-027A_market_aware_kline_storage_and_download.md) | Not started | Not yet verified |
| D3, D4 | [`EPIC-027B`](incomplete/EPIC-027B_spot_mode_in_the_backtest_engine.md) | Not started | Not yet verified |
| D5 | [`EPIC-027C`](incomplete/EPIC-027C_exchange_filters_on_simulated_fills.md) | Not started | Not yet verified |
| D6 | [`EPIC-027F`](incomplete/EPIC-027F_venue_selected_trading_client_factory.md), [`EPIC-027K`](incomplete/EPIC-027K_spot_trading_client_and_order_path.md) | Not started | Not yet verified |
| D7 | [`EPIC-027H`](incomplete/EPIC-027H_spot_account_reader_and_holdings_model.md) | Not started | Not yet verified |
| D8 | [`EPIC-027G`](incomplete/EPIC-027G_spot_testnet_venue_and_credentials.md) | Not started | Not yet verified |
| D9 | [`EPIC-027N`](incomplete/EPIC-027N_live_strategy_on_spot.md) | Not started | Not yet verified |
