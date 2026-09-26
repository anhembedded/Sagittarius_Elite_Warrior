# EPIC-027 — Spot beside Futures: truthful Spot backtests first, then live Spot on Testnet

- **Status:** 🟡 Phase 1 in progress — the user accepted the ADR (D1–D9) and every recommended answer (O1–O6) on 2026-09-26. `EPIC-027A` is the current task.
- **Repositories:** Elite. No Engine change is expected.
- **Origin:** the user (2026-09-26): *"đánh giá xem giờ tui muốn giao dịch spot và back test theo
  spot thì app này cần những gì, lên plan và epic, sao đó report cho tôi"* ("assess what this app
  needs now that I want to trade spot and backtest on spot; make a plan and an epic, then report to
  me").
- **North star:** [`Docs/HLD/`](../../../Docs/HLD/README.md) for the module boundaries every sub-task
  respects: `market_data` owns candles, `backtesting` owns the simulator, `trading` owns submission,
  and `support/binance_gateway` is the one anticorruption layer around the SDK. When the ADR below is
  accepted, its decisions become a section of the HLD in the same pull request as `EPIC-027A`.
- **Decisions:** [`DECISION_2026-09-26_spot_market_axis.md`](DECISION_2026-09-26_spot_market_axis.md)
  (D1–D9 Accepted, O1–O6 answered — 2026-09-26).
- **Tracking (Gantt, PR matrix):** [`TRACKING.md`](TRACKING.md).
- **Dependencies:**
  - It revisits [`EPIC-021`'s ADR](../EPIC-021_ket_noi_binance_futures_testnet/DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md)
    §1 (Futures chosen over Spot) by adding Spot beside Futures, not by reversing it.
  - [`EPIC-026`](../EPIC-026_road_to_real_money/README.md) lists Spot as out of its scope. Spot mainnet
    goes through `EPIC-026`'s gates (ADR O5), not through this epic.
  - `EPIC-027F`'s factory is the same seam `EPIC-026P` needs for Futures mainnet. Whichever lands
    first builds it; the other adds one row.

---

## 1. Decisions already made
All nine are accepted (🟢 user decision, 2026-09-26), and all six open questions are answered with
their recommended option — see the ADR §4. The ones that shape the plan are:
1. **Market type is an explicit axis** (D1). The unused `MarketType` enum moves to the shared kernel,
   and stored candles are keyed by market (D2).
2. **Spot in the backtest = long-only, 1×, no liquidation** (D3). The existing 1× LONG arithmetic is
   reused. SHORT/COVER signals are dropped, counted and reported, never remapped (D4).
3. **Exchange filters apply to every simulated fill**, in both markets (D5).
4. **Live Spot is a second adapter set behind the same ports.** It comes after a behavior-preserving
   refactor that routes six direct client constructions through one factory (D6).
5. **A Spot "position" is a holding**, with balances and no invented mark or liquidation price (D7).
6. **Live Spot starts on Spot Testnet only** (D8), for **USDT-quoted pairs only** (D9).

## 1.1 What the tree already has (measured 2026-09-26, `ee7105f8`)

| Capability | Where |
| :--- | :--- |
| 1× LONG valued and settled with spot arithmetic; no liquidation | `backtesting/domain/policies/margin_risk_policy.py:103,160,182` |
| BUY/SELL already mean "open long"/"close long"; SHORT/COVER are separate | `strategy/contracts/signal_action.py` |
| Default commission 0.1 % = Spot base rate; quote-currency charging is numerically equivalent | `backtesting/domain/policies/fee_calculator_policy.py:28-71` |
| Spot exchange filters parsed from `/api/v3/exchangeInfo` (for backtest hints) | `market_data/adapters/binance/market_metadata_parser.py:21-42` |
| Spot klines downloaded on the default venue | `support/binance_gateway/contracts/binance_endpoints.py:52` |
| Exchange-agnostic Decimal lot/tick rounding | `trading/domain/policies/order_quantity_rounding_policy.py:87-130` |
| An (unused) `MarketType {SPOT, FUTURES_USD_M, FUTURES_COIN_M}` | `src/domain/value_objects/market_type.py:10` |
| `IAccountSnapshot` already documents "Spot answers None for futures-only fields" | `trading/contracts/i_account_snapshot.py:21-25` |
| python-binance's `testnet=True` already routes Spot calls to `testnet.binance.vision` | `binance_endpoints.py:42-45` |

## 1.2 What the tree does not have

- **Backtest:**
  - no market switch;
  - no way to refuse shorts;
  - no exchange-filter rounding (quantities are unrounded floats);
  - candles not tagged by market.
- **Truth finding:** today's leveraged, short-capable "Futures" backtests on the default venue run on
  **Spot** prices, and nothing on screen says so. See the ADR §1.
- **Live:** everything is Futures-only:
  - `futures_*` session protocol;
  - `TradingVenue {DISABLED, FUTURES_TESTNET}`;
  - positions with `reduce_only`, mark price and liquidation price;
  - the Futures user data stream;
  - Futures metadata;
  - a fake exchange with only three unsigned Spot GETs;
  - an inert Dev Board market combo.

## 2. Goals — measurable

| Metric | Today (measured 2026-09-26) | When the epic is done |
| :--- | :-: | :-: |
| Stored candles whose market is recorded | 0 % | 100 % (legacy migrated per O3) |
| Futures backtests that run on Futures prices (default venue) | 0 — they use Spot klines | all |
| Backtest market types selectable on screen | 1 (implicit Futures) | 2 (Spot, USDⓈ-M) |
| Simulated fills that respect step size and minimum notional | 0 | all, recorded in the report |
| Short positions a Spot backtest can open | unbounded (no gate) | 0, with the ignored count reported |
| Application-layer sites that construct a trading client directly | 6 | 0 (one factory) |
| `TradingVenue` members that route to Spot | 0 | 1 (`SPOT_TESTNET`) |
| Fake-exchange Spot routes able to fill a signed order | 0 | the full order lifecycle + user data stream |
| Proven real Spot Testnet round trips (BUY → holding → SELL) | 0 | 1, pasted into `EPIC-027P` |

## 3. Sub-tasks, ordered by risk
Phases are the gates, and within a phase the order is by risk and dependency. Every task is one pull
request unless its file says otherwise.

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| **Phase 1 — Spot backtest (no API keys needed)** | | | | | |
| [EPIC-027A](incomplete/EPIC-027A_market_aware_kline_storage_and_download.md) | Every stored candle knows its market; a sync asks for one | Elite | O3 (answered) | 🔴 | In progress |
| [EPIC-027B](incomplete/EPIC-027B_spot_mode_in_the_backtest_engine.md) | Spot mode in the engine: long-only, 1×, never liquidated, shorts counted | Elite | A | 🟡 | Planned |
| [EPIC-027C](incomplete/EPIC-027C_exchange_filters_on_simulated_fills.md) | Simulated fills obey step size, minimum notional and tick size | Elite | A | 🟡 | Planned |
| [EPIC-027D](incomplete/EPIC-027D_backtest_ui_market_selector.md) | Backtest screen chooses the market and shows only what it can do | Elite | A, B | 🟢 | Planned |
| [EPIC-027E](incomplete/EPIC-027E_report_schema_carries_market_type.md) | Saved reports state their market | Elite | B, C | 🟢 | Planned |
| **Phase 2 — Live Spot foundations (read-only)** | | | | | |
| [EPIC-027F](incomplete/EPIC-027F_venue_selected_trading_client_factory.md) | One venue-selected factory replaces six direct client constructions | Elite | None | 🔴 | Planned |
| [EPIC-027G](incomplete/EPIC-027G_spot_testnet_venue_and_credentials.md) | `TradingVenue.SPOT_TESTNET`, own keys, market-mismatch alignment | Elite | F | 🟡 | Planned |
| [EPIC-027J](incomplete/EPIC-027J_fake_exchange_spot_routes.md) | Fake exchange answers the Spot API (signed orders, account, stream) | Elite | None | 🟡 | Planned |
| [EPIC-027H](incomplete/EPIC-027H_spot_account_reader_and_holdings_model.md) | Spot account read as balances and holdings | Elite | G, J, O6 | 🟡 | Planned |
| [EPIC-027I](incomplete/EPIC-027I_spot_symbol_metadata_provider.md) | Spot exchange filters for live rounding | Elite | G | 🟢 | Planned |
| **Phase 3 — Live Spot orders on Testnet** | | | | | |
| [EPIC-027K](incomplete/EPIC-027K_spot_trading_client_and_order_path.md) | Spot MARKET/LIMIT orders through `ExecuteOrderCommand` | Elite | F, G, I, J | 🔴 | Planned |
| [EPIC-027L](incomplete/EPIC-027L_spot_user_data_stream.md) | Spot order truth and balances from the user data stream | Elite | H, K | 🔴 | Planned |
| [EPIC-027M](incomplete/EPIC-027M_spot_session_enable_and_emergency_stop.md) | Enable, Emergency Stop and limits mean the right thing on Spot | Elite | K, L | 🔴 | Planned |
| [EPIC-027N](incomplete/EPIC-027N_live_strategy_on_spot.md) | Armed strategy trades Spot long-only at 1× | Elite | M, O2, O4 | 🟡 | Planned |
| [EPIC-027O](incomplete/EPIC-027O_live_ui_for_spot.md) | Trading screen and Dev Board show Spot holdings, Buy/Sell only | Elite | L, N | 🟢 | Planned |
| [EPIC-027P](incomplete/EPIC-027P_spot_testnet_tier_and_spec.md) | Real Spot Testnet round trip proven; Spot order lifecycle SPEC | Elite | K–O | 🟡 | Planned |

## 4. Phase exit criteria

| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| Phase 1 | A Spot backtest and a Futures backtest of the same symbol run on their own market's candles. The Spot one never shorts or liquidates. Both round quantities to exchange filters and state it in the report. | The golden Futures run unchanged byte-for-byte (except where `EPIC-027C`'s filters change it, and then recorded); the integration test of `EPIC-027D`; the full gate green on GitHub Actions. Not run. |
| Phase 2 | `exchange-status` against Spot Testnet shows balances with a Spot key and refuses a Futures key as a key error. No application-layer file constructs a trading client. | `EPIC-027F`'s architecture guard; `EPIC-027H`'s CLI output pasted into its task file. Not run. |
| Phase 3 | A human BUY and SELL, and an armed long-only strategy, each round-trip on Spot Testnet. Emergency Stop never sells a pre-existing holding. | `EPIC-027P`'s tier output from the user's run; `EPIC-027M`'s baseline test; the SPEC listed as ✅ in `Docs/SPEC/README.md`. Not run. |

## 5. Out of scope

- **Spot mainnet.** It enters as its own reviewed `TradingVenue` member through `EPIC-026`'s gates
  (journal, breaker, soak, typed acknowledgement), the same way Futures mainnet does (ADR O5).
- **Margin (cross/isolated) Spot trading**, i.e. borrowing to short on Spot. It is a third market with
  its own API.
- **COIN-M futures.**
- **Non-USDT quote assets** (ADR D9, O4).
- **Exchange-side protective orders on Spot** (OCO, `STOP_LOSS_LIMIT`). `EPIC-026K` owns protective
  stops; a Spot variant follows it.
- **BNB fee discount** and maker/taker split in the simulator.
- **Funding-rate modeling for Futures.** Still out of scope as in `BOT-049`.

## Notes (newest first)
- **2026-09-26** — Epic scaffolded from two independent audits of the tree (live path, backtest
  path). The ADR was Accepted the same day, with every open question answered per its recommended
  option; `EPIC-027A` is now in progress.
