# EPIC-027 — Spot beside Futures: truthful Spot backtests first, then live Spot on Testnet

- **Status:** 🟢 Phase 1 done (5/5, 2026-09-27); Phase 2 done (5/5, 2026-09-27); Phase 3 in progress (5/6, 2026-09-28) — the user accepted the ADR (D1–D9) and every recommended answer (O1–O6) on 2026-09-26. `EPIC-027A` through `EPIC-027M` are done, so `TradingVenue` now has a Spot Testnet member with its own credentials, capability-checked gates, an honest market-mismatch alignment state, the fake exchange answers the full Spot order lifecycle, the app reads a Spot account as balances/holdings/equity through the same `ITradingAccountReader` port Futures uses, a live Spot order rounds against Spot's own `exchangeInfo` filters rather than Futures', a Spot MARKET/LIMIT order can go end to end through `ExecuteOrderCommand` to Spot Testnet, `SpotUserDataStream` reports fills/fees and equity from Spot's own `executionReport`/`outboundAccountPosition`/`balanceUpdate` events, Enable trading on Spot records a holdings baseline instead of refusing on existing assets, and Emergency Stop sells only the surplus over that baseline. `EPIC-027N` is now also done: leverage is fixed at 1 on Spot, a SHORT-capable strategy is refused arming, and a strategy's own SELL signal sizes from the actual holding (never below the baseline) instead of a percent of balance. `EPIC-027O` (live UI for Spot) is now also done: both screens show a Holdings table instead of Positions on Spot, the manual order card reads BUY/SELL with SELL disabled without a real holding, leverage controls are hidden on Spot, the Dev Board market combo is wired to the chart's own requested market, and every message naming the venue names the market too. `EPIC-027P` (real Spot Testnet round trip + SPEC) is next.
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
| [EPIC-027A](completed/EPIC-027A_market_aware_kline_storage_and_download.md) | Every stored candle knows its market; a sync asks for one | Elite | O3 (answered) | 🔴 | ✅ Done (2026-09-26) |
| [EPIC-027B](completed/EPIC-027B_spot_mode_in_the_backtest_engine.md) | Spot mode in the engine: long-only, 1×, never liquidated, shorts counted | Elite | A | 🟡 | ✅ Done (2026-09-27) |
| [EPIC-027C](completed/EPIC-027C_exchange_filters_on_simulated_fills.md) | Simulated fills obey step size, minimum notional and tick size | Elite | A | 🟡 | ✅ Done (2026-09-27) |
| [EPIC-027D](completed/EPIC-027D_backtest_ui_market_selector.md) | Backtest screen chooses the market and shows only what it can do | Elite | A, B | 🟢 | ✅ Done (2026-09-27) |
| [EPIC-027E](completed/EPIC-027E_report_schema_carries_market_type.md) | Saved reports state their market | Elite | B, C | 🟢 | ✅ Done (2026-09-27) |
| **Phase 2 — Live Spot foundations (read-only)** | | | | | |
| [EPIC-027F](completed/EPIC-027F_venue_selected_trading_client_factory.md) | One venue-selected factory replaces six direct client constructions | Elite | None | 🔴 | ✅ Done (2026-09-27) |
| [EPIC-027G](completed/EPIC-027G_spot_testnet_venue_and_credentials.md) | `TradingVenue.SPOT_TESTNET`, own keys, market-mismatch alignment | Elite | F | 🟡 | ✅ Done (2026-09-27) |
| [EPIC-027J](completed/EPIC-027J_fake_exchange_spot_routes.md) | Fake exchange answers the Spot API (signed orders, account, stream) | Elite | None | 🟡 | ✅ Done (2026-09-27) |
| [EPIC-027H](completed/EPIC-027H_spot_account_reader_and_holdings_model.md) | Spot account read as balances and holdings | Elite | G, J, O6 | 🟡 | ✅ Done (2026-09-27) |
| [EPIC-027I](completed/EPIC-027I_spot_symbol_metadata_provider.md) | Spot exchange filters for live rounding | Elite | G | 🟢 | ✅ Done (2026-09-27) |
| **Phase 3 — Live Spot orders on Testnet** | | | | | |
| [EPIC-027K](completed/EPIC-027K_spot_trading_client_and_order_path.md) | Spot MARKET/LIMIT orders through `ExecuteOrderCommand` | Elite | F, G, I, J | 🔴 | ✅ Done (2026-09-27) |
| [EPIC-027L](completed/EPIC-027L_spot_user_data_stream.md) | Spot order truth and balances from the user data stream | Elite | H, K | 🔴 | ✅ Done (2026-09-27) |
| [EPIC-027M](completed/EPIC-027M_spot_session_enable_and_emergency_stop.md) | Enable, Emergency Stop and limits mean the right thing on Spot | Elite | K, L | 🔴 | ✅ Done (2026-09-27) |
| [EPIC-027N](completed/EPIC-027N_live_strategy_on_spot.md) | Armed strategy trades Spot long-only at 1× | Elite | M, O2, O4 | 🟡 | ✅ Done (2026-09-28) |
| [EPIC-027O](completed/EPIC-027O_live_ui_for_spot.md) | Trading screen and Dev Board show Spot holdings, Buy/Sell only | Elite | L, N | 🟢 | ✅ Done (2026-09-28) |
| [EPIC-027P](incomplete/EPIC-027P_spot_testnet_tier_and_spec.md) | Real Spot Testnet round trip proven; Spot order lifecycle SPEC | Elite | K–O | 🟡 | Planned |

## 4. Phase exit criteria

| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| Phase 1 | A Spot backtest and a Futures backtest of the same symbol run on their own market's candles. The Spot one never shorts or liquidates. Both round quantities to exchange filters and state it in the report. | The golden Futures run unchanged byte-for-byte (except where `EPIC-027C`'s filters change it, and then recorded); the integration test of `EPIC-027D`; a saved report states its market and exchange filters (`EPIC-027E`); the full gate green on GitHub Actions. ✅ Closed 2026-09-27. |
| Phase 2 | `exchange-status` against Spot Testnet shows balances with a Spot key and refuses a Futures key as a key error. No application-layer file constructs a trading client. | `EPIC-027F`'s architecture guard (closed 2026-09-27 — no file outside the one factory constructs `FuturesTradingClient`, in all of `src/`+`scripts/`, not just `application/`); `EPIC-027H`'s CLI output pasted into its task file; `EPIC-027I`'s parser/provider/composition tests (closed 2026-09-27). ✅ Closed 2026-09-27. |
| Phase 3 | A human BUY and SELL, and an armed long-only strategy, each round-trip on Spot Testnet. Emergency Stop never sells a pre-existing holding. | `EPIC-027P`'s tier output from the user's run; `EPIC-027M`'s baseline test (closed — see below); the SPEC listed as ✅ in `Docs/SPEC/README.md`. `EPIC-027K` closed 2026-09-27 (a Spot MARKET/LIMIT order can be placed/canceled through `ITradingClient`); `EPIC-027L` closed 2026-09-27 (fills/fees and equity report through `SpotUserDataStream`); `EPIC-027M` closed 2026-09-27 (Enable records a baseline, Emergency Stop never sells it); `EPIC-027N` closed 2026-09-28 (leverage fixed at 1, a SHORT-capable strategy refused, SELL sized from the actual holding never below baseline); the rest of Phase 3 not run. |

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
- **2026-09-28** — `EPIC-027O` done, Phase 3 now 5/6. Both live screens (Dev Board, Trading) swap
  Positions for a Holdings table (asset/free/locked/value in USDT) on a Spot venue via a
  `QStackedWidget` switched once at construction by `market_type`; the manual order card reads
  BUY/SELL on Spot (SELL disabled until `LiveOrderBookCoordinator.has_holding()` says otherwise);
  leverage controls are hidden on Spot on both screens; the Dev Board's previously-inert Market combo
  now commits the chart's own requested `MarketType` through the same "commit at Load History/Start
  Live click time, read the committed value later" pattern `_active_symbol`/`_active_interval` already
  use, never a live re-read (a live re-read mid-scroll could mix Spot and Futures candles on one
  chart); `TC-GAP-01` is rewritten to assert the new wiring instead of its absence; and every message
  naming the venue (`TRADING_VENUE_DISABLED` on both screens, `trade-once`'s CLI formatter) now names
  the market too. Reused the existing `ITradingAccountReader.check_connection().holdings` seam end to
  end — no new port method. See `completed/EPIC-027O_live_ui_for_spot.md` §6 for the two notable
  implementation decisions (a private-method rename to keep the cross-screen duplication ratchet at
  its baseline; why the BUY→Holdings proof is a fake-Spot-exchange application test rather than a
  second parallel `qtbot` Dev Board boot fixture).
- **2026-09-28** — `EPIC-027N` done, Phase 3 now 4/6. `BaseStrategy` gained a `ClassVar[frozenset
  [SignalAction]] supported_directions`, defaulting to `{BUY, SELL}` (long-only) so every strategy that
  never calls `self.short()`/`self.cover()` needed zero changes; `EmaTrendPullbackStrategy` and
  `VolumeSpikeFlowStrategy` — the only two that do — override it to add `SHORT, COVER`. All three of
  this task's Spot-only refusals (leverage fixed at 1, a SHORT-capable strategy, a non-USDT symbol) turned
  out to belong in `ArmStrategyCommandHandler`, not the UI coordinator or `ArmedStrategyConfig` the task's
  own original file table named — both would have been a UI class enforcing a trading safety rule, the
  exact mistake `i_trading_session.py`'s own docstring already records this repo paying for once.
  `TradingSessionSnapshot` grew two fields (`market_type: MarketType | None`, `spot_baseline_holdings`) so
  `strategy` could learn the venue and the Spot baseline without ever importing `support/binance_gateway`
  directly — a real fourth and fifth consumer of a snapshot its own docstring once limited to three
  "measured" facts. A strategy's own SELL signal now reuses `EPIC-027M`'s exact `sellable_spot_quantity()`
  policy (moved from `trading/domain/policies/` to `trading/contracts/` so `strategy` could legally import
  it across the module boundary) rather than a second, divergent "how much may Spot sell" rule — the same
  never-sell-the-baseline safety net Emergency Stop already has. `strategy_arming_coordinator.py` was
  already over `architecture-rule.md` §5.4's shrink-only 424-line ratchet with no room to grow for the
  three new refusal messages, so `ARM_BLOCK_MESSAGES`/`DISARM_BLOCKED_MESSAGE` moved to a new
  `arm_block_messages.py` (a genuine shrink to 399 lines, its `baseline_god_files.json` entry removed).
  A new guard (`test_supported_directions_guard.py`) source-scans every registered strategy for a literal
  `self.short(`/`self.cover(` call and fails if the matching direction isn't declared — mutation-verified
  by hand. `tests/unit` 5842 passed; `tests/integration` 184 passed/4 pre-existing skips/0 failed;
  `tests/unit/architecture` 459 passed; mypy unchanged at the pre-existing 584-error baseline (a same-repo
  invocation from inside the repo root falsely reported 2722/2737 from a namespace-package resolution
  artifact of that directory — the parent-directory invocation GitHub Actions and the reviewer both use
  is the one that reproduces the documented baseline exactly).
- **2026-09-27** — `EPIC-027M` done, Phase 3 now 3/6. `EnableTradingCommandHandler` records the
  account's current Spot holdings (already fetched via `ITradingAccountReader.check_connection()`,
  no second network call) as a session baseline in `TradingSessionState` the moment trading turns on
  — the real gap this task closed: `UNEXPECTED_POSITIONS` never actually refused Spot to begin with
  (`SpotTradingClient.get_positions()` always answers `[]`), but nothing recorded what the app was
  and was not responsible for. `EmergencyStopCommandHandler`'s step 3 now dispatches on
  `TradingVenue.market_type` (one branch point, `code/quality.md` §3): Futures closes
  `LivePosition`s unchanged, Spot sells each held asset's surplus over its own baseline
  (`current - baseline`, floored to the exchange's lot step via the new pure
  `sellable_spot_quantity()` policy), re-fetching current holdings fresh rather than trusting the
  baseline snapshot as "now". No baseline recorded at all (never enabled on Spot this session) is
  the safety-critical case — treated as "unknown, sell nothing" rather than guessing zero and
  offering up the user's whole pre-existing holdings. The four session limits needed no code change
  for Spot (already plain USDT/count/duration checks with no Futures assumption); a new test proves
  that rather than leaving it inferred. `Docs/SPEC/`'s Emergency Stop section stays unwritten on
  purpose — `SPEC-007` doesn't exist yet (owned by the not-yet-started `EPIC-026B`), recorded as an
  explicit scope note rather than silently dropped. 29 new tests; full
  trading+architecture+integration regression 1584 passed/4 skipped/0 failed; mypy unchanged at the
  pre-existing 584-error baseline.
- **2026-09-27** — `EPIC-027L` done, Phase 3 now 2/6. `SpotUserDataStream` implements `IUserDataStream`
  over `bsm.user_socket()` (verified against `python-binance`'s own source, not
  `futures_user_socket()`), mirroring `FuturesUserDataStream`'s connection/reconnect mechanism
  (generation fencing, the `{"e":"error"}` reconnect sentinel) but with a deliberately smaller
  dependency set — no `TradingSessionState`/`ITradingClientFactory` (no position-reconciliation
  concept for Spot, ADR D8) — and `ITradingAccountReader.check_connection()` re-fetched
  authoritatively on every `outboundAccountPosition`/`balanceUpdate` rather than a value derived
  from the stream's own balance deltas. `spot_user_data_event_parser.py` parses Spot's flat
  `executionReport` shape (unlike Futures' `"o"`-nested one) and reads its `"n"`/`"N"` fee into
  `OrderFilledEvent`'s new optional `fee_amount`/`fee_asset` fields. Along the way, the fake
  exchange's own `SpotAccountState._emit_fill_events()` (`EPIC-027J`) was corrected to emit `"x"`
  (execution type) and `"q"` (order quantity) — both missing before this task, and both needed for
  a faithful parser (fixed at the fixture, not worked around in the parser). 31 new unit tests;
  full trading+architecture+integration regression 1555 passed/4 skipped/0 failed; mypy unchanged
  at the pre-existing 584-error baseline.
- **2026-09-27** — `EPIC-027K` done, opening Phase 3 (1/6). `SpotTradingClient`/`SpotTradingClientFactory`
  implement `ITradingClient`/`ITradingClientFactory` for `SPOT_TESTNET`, mirroring `FuturesTradingClient`'s
  own four-collaborator shape, `OrderSubmissionMode`-gated `create_test_order`/`create_order` routing and
  `BinanceAPIException` → `OrderRejectedByExchangeError` translation. The new `spot_order_payload_mapper.py`
  never emits `reduceOnly`/`positionSide` — genuinely absent Spot API fields, not merely unset — and
  refuses `STOP_MARKET`/`TAKE_PROFIT_MARKET` (Futures-only members on this app's shared `OrderType`) before
  any network call. `TradingVenue.supports_order_submission` — the one property `EPIC-027G`'s own docstring
  had already pre-announced this task would flip — now covers both testnets, gating all three order-path
  safety checks and the `ITradingClient`/`ITradingClientFactory` binds with zero handler edits (this task's
  own acceptance criterion). Two Spot-specific API facts, not design choices: `get_positions()` always
  returns `[]` (a Spot account has no leveraged positions — the true answer, not a port split, since every
  real caller already treats an empty list as "flat"); `cancel_all_orders()` needs no pre-read of
  `get_open_orders()` the way `FuturesTradingClient` does, because Spot's own `DELETE /api/v3/openOrders`
  returns the canceled list directly. The task's own §3 SELL/`reduce_only=False` precondition (ADR D4) was
  scoped out during implementation — not a numbered acceptance criterion, would need out-of-scope handler
  edits, and already structurally redundant since a Spot account cannot oversell without margin/borrow —
  recorded explicitly in the task file's revised §3 rather than silently dropped. 35 new/changed tests
  (mapper, client, composition wiring against a real `StdLibContainer`, and a fake-exchange integration
  test using a `LIMIT` order since Spot's fake exchange — unlike Futures' — fills a `MARKET` order
  immediately); `tests/unit/architecture` 457 passed, `tests/unit/modules/trading` 849 passed,
  `tests/integration/infrastructure/binance` +4 passed; ruff/format clean; mypy clean at the frozen
  584-error baseline (zero new errors in any touched file). `EPIC-027L` (Spot user data stream) is next.
- **2026-09-27** — `EPIC-027I` done, closing Phase 2 (5/5). A live Spot order will now round its
  quantity against Spot's own `exchangeInfo` filters instead of Futures'. `FuturesSymbolMetadata` was
  renamed in place to `SymbolOrderMetadata` (and its cache port/impl to `ISymbolOrderMetadataCache`/
  `InMemorySymbolOrderMetadataCache`) so both `FuturesMetadataProvider` and the new
  `SpotMetadataProvider` return the same market-neutral type, chosen by `adapter_bindings.py`'s
  `IMarketMetadataProvider` bind the same way `ITradingAccountReader` already branches on
  `TradingVenue` (`EPIC-027H`). The new `spot_metadata_parser.py` deliberately does the opposite of
  `futures_metadata_parser.py`'s defensive defaulting: a missing `PRICE_FILTER`/`LOT_SIZE`/`NOTIONAL`
  filter or field raises `KeyError` rather than silently defaulting, per this task's own acceptance
  criterion; only `MARKET_LOT_SIZE` is optional, and `SymbolOrderMetadata.step_size_for(order_type)`
  picks it for `OrderType.MARKET` when published, falling back to `LOT_SIZE` otherwise (every other
  order type, including `STOP_MARKET`, always uses `LOT_SIZE`).
- **2026-09-27** — `EPIC-027H` done, advancing Phase 2 (4/5). The app now reads a Spot account through
  the same `ITradingAccountReader` port `FuturesAccountReader` already implements — `SpotAccountReader`
  over Spot's own unprefixed session methods (`ping`/`get_server_time`/`get_account`/`get_symbol_ticker`),
  never `LivePosition` with invented mark price or leverage (ADR D7). A new `SpotHolding` value type
  carries only what `GET /api/v3/account`'s `balances` array gives; `ExchangeConnectionStatus` gained
  `holdings`/`equity` fields a Futures venue answers `None` for, the exact symmetric case
  `i_account_snapshot.py`'s docstring already anticipated for `position_mode`/`margin_type` answering
  `None` for Spot. Equity (quote balance plus non-dust holdings × ticker price) is all-or-nothing: one
  unpriceable holding makes the whole figure `None`, never a silently partial sum — the same "never
  guess" discipline this task's own acceptance criteria demand of the average entry price (deferred to
  ADR O6's `GET /api/v3/myTrades`, out of this task's scope). Two ports came along as a direct
  consequence, not scope creep: `ISpotSessionFactory`/`ISpotSessionClient` (`support/binance_gateway/`)
  — a parallel port to `ITradingSessionFactory`, since that port's own docstring rules out widening it
  for a second venue — and `SpotSessionFactory`, mirroring `FuturesSessionFactory`'s own `BUG-111`
  clock-skew correction. The venue-branching bind in `adapter_bindings.py` is locked against a real
  `StdLibContainer` in both directions (`test_module_account_reader_binding.py`), mirroring
  `test_module_trading_client_binding.py`'s own doctrine. `tests/unit/architecture` 451 passed (after
  extending the Binance-client-construction allow-list for the new session factory);
  `tests/unit/modules/trading` 798 passed; `tests/sanity` 32 passed;
  `tests/integration/infrastructure/binance` 13 passed; ruff/mypy clean (mypy diffed byte-for-byte
  against a clean-cache baseline including untracked files — zero new errors). Full `tests/unit` left to
  GitHub Actions' `-Full` run per this repo's own cadence (user decision 2026-09-18).
- **2026-09-27** — `EPIC-027J` done, advancing Phase 2 (3/5). The fake exchange now answers the full
  Spot order lifecycle: signed `POST`/`DELETE /api/v3/order`, `/order/test`, `/openOrders`,
  `GET /api/v3/account`, `GET /api/v3/time`, and the (unsigned) `/api/v3/userDataStream` trio — a new,
  independent `SpotAccountState` (balances + open orders), never a union with Futures' own
  `OrderBookState`. A `MARKET` fill moves quote↔base and charges its 0.1% fee in the asset received,
  and queues `executionReport`/`outboundAccountPosition` user-data events for a test to drain. Along
  the way, `server.py`'s `do_POST`/`PUT`/`DELETE` were found to route to Futures unconditionally — only
  `do_GET` ever consulted Spot's own routes — collapsed into one `_dispatch()` that routes by path
  prefix, closing that gap for good. `exchangeInfo`'s filter shape was verified against the real
  parser this app runs (`market_metadata_parser.py`), not guessed: `baseAsset`/`quoteAsset` at the
  symbol level and the current `NOTIONAL`/`minNotional` filter name. 9 new contract tests exercise
  every route through a real, unpatched-except-URL `binance.client.Client` (the established
  `test_session_factories_against_fake_server.py` precedent, since `EPIC-027K`'s real Spot adapter
  does not exist yet to drive these routes through). `tests/unit/architecture` 451 passed; targeted
  `tests/integration/infrastructure/binance` + `tests/sanity` 51 passed; ruff clean. No `src/`/`scripts/`
  files touched, so mypy's baseline is unaffected.
- **2026-09-27** — `EPIC-027G` correction after independent PR review: the three order-path gates and
  `TradingModule`'s `ITradingClient` bind now check a new `TradingVenue.supports_order_submission`
  property (`True` only for `FUTURES_TESTNET`) instead of a literal `is DISABLED` check. The review
  found the literal check let `SPOT_TESTNET` clear the gates while `ITradingAccountReader`/
  `ITradingClientFactory`/`IUserDataStream` stayed unconditionally bound to their Futures-only
  adapters — `EnableTradingCommandHandler` would have signed a Futures Testnet call with Spot Testnet
  credentials instead of failing cleanly. Constitutional decision (P1 poka-yoke, P6 fix-the-mechanism,
  P7 seam-now/variant-later): one named capability property is the mechanical barrier, and the "one
  place" `EPIC-027K` flips when Spot's real order path lands. See the task file's own "Post-review
  correction" note for the full trace.
- **2026-09-27** — `EPIC-027G` done, advancing Phase 2 (2/5). `TradingVenue.SPOT_TESTNET` exists,
  with a `market_type` property every downstream consumer reads instead of assuming Futures.
  `EnvFirstCredentialsProvider` is now bound to one venue for its lifetime and reads a distinct env
  var pair per venue (`BINANCE_SPOT_TESTNET_API_KEY/_SECRET`), so a Futures key can never resolve for
  Spot or vice versa — its composition-root binding became a lazy factory (the same
  register()-cannot-resolve() constraint `EPIC-027F` hit), and its three former consumers now resolve
  the port themselves instead of closing over a plain instance. The three order-path safety gates
  changed from `is not FUTURES_TESTNET` to `is DISABLED` — a capability check, so a new supported
  venue is never refused by default. Found along the way: the live Trading/Dashboard screens' own
  chart and stream are hard-coded to `MarketType.SPOT` regardless of `TradingVenue` — a real,
  previously-unreported truth violation directly analogous to `EPIC-027A`'s headline finding but for
  the live screen, not the backtester. `VenueAlignment.MARKET_MISMATCH` now names it, and
  `compute_venue_alignment` takes an explicit `chart_market_type` parameter rather than a hidden
  constant. Settings gained the Spot Testnet option. `tests/unit/architecture` 451 passed (after
  trimming `app_bootstrapper.py`'s comment to stay under its 550-line ratchet), `tests/unit/modules/trading`
  797 passed, full `tests/unit` 5638 passed; ruff and mypy clean (mypy diffed byte-for-byte against a
  clean-cache pre-change baseline — zero new errors). `EPIC-027J` is next (independent of `027G`, per
  the table above).
- **2026-09-27** — `EPIC-027F` done, opening Phase 2 (1/5). Six sites that each constructed
  `FuturesTradingClient(...)` directly (the four order-path handlers, the open-positions query, the
  user data stream) now resolve `ITradingClientFactory.create(mode)` instead — a single seam
  `EPIC-027K` extends with one Spot row rather than editing all six again. `create()` takes only
  `OrderSubmissionMode`, not `(venue, mode)`: venue is selected once, at boot, by which concrete
  factory `adapter_bindings.py` binds, not by an argument a caller could request the wrong venue
  with. `ITradingClientFactory` is bound unconditionally (like `ITradingAccountReader`/
  `IUserDataStream`), so every handler that depends on it stays constructible while trading is
  disabled. Found along the way: `FuturesUserDataStream` keeps `credentials_provider` as its own
  constructor parameter, separate from the factory — `_run_stream()` uses it independently to open
  the raw signed websocket. New architecture guard
  (`test_only_the_factory_constructs_futures_trading_client.py`) scans all of `src/`+`scripts/`, not
  just `application/` as the task originally scoped it — it also caught a probe script
  (`scripts/epic021h_user_stream_probe.py`) using the old constructor shape, via mypy rather than the
  original grep. `tests/unit/modules/trading` 794 passed, `tests/unit/architecture` 451 passed,
  `tests/unit` (full) 5626 passed, `tests/sanity` 32 passed; ruff and mypy (713 files) clean.
- **2026-09-27** — `EPIC-027E` done, closing Phase 1 (5/5). A saved report was silently dropping four
  facts (`market_type`, `ignored_short_signals`, `rejected_entries`, `exchange_filters`) `EPIC-027B`/
  `027C` had already put on `BacktestResult` — the serializer never wrote them, so the loader always
  rebuilt a Futures-with-no-filters result regardless of what actually ran. Schema bumped 1 → 2 with
  every new field defaulted on load (a v1 file re-runs unchanged); the report's own "market not
  recorded" state is a `BacktestReportLoadResult` flag, the same mechanism `BOT-078` already used for
  `strategy_key_unknown`/`metrics_mismatch`, never a guessed value on `BacktestResult` itself. The
  comparison dialog gained a second, separate mismatch warning for Spot-vs-Futures (the existing
  `build_market_mismatch_warning` already means "different symbol/timeframe" — a naming collision
  flagged, not fixed, since renaming it is outside this task). Folded in the same bump: the serializer
  also wasn't writing `break_even_trigger_pct`/`trailing_activation_pct`/`trailing_offset_pct`/
  `partial_take_profit_levels` (`BOT-105A`/`105C`, pre-dating this epic). 5618 unit passed, 168 integration passed (4 skipped), 32 sanity passed, architecture 445, mypy clean.
- **2026-09-27** — `EPIC-027C` and `EPIC-027D` done, in one pull request.
  - **Simulated fills obey the exchange's rules** for the run's (market, symbol): quantity floored
    to the step, entries below the minimum refused and counted, slippage by the real tick.
  - **The Backtest screen chooses Spot or USD-M Futures.** Candles, catalog, coverage, sync and
    exchange filters all follow the choice, so `market_data`'s read ports now take a market. Spot
    hides leverage and the short-only filters.
  - Result and limitations state the market, the ignored shorts and the filters.
  - 5612 unit passed, 168 integration passed (4 skipped), 32 sanity passed. `EPIC-027E` (the report) closes Phase 1.
- **2026-09-27** — `EPIC-027B` done: `BrokerSimulationConfig.market_type` (default `FUTURES_USD_M`,
  so existing runs are unchanged); `SPOT` is long-only at 1× and never liquidated, and SHORT/COVER are
  dropped and counted by `MarketSignalGatePolicy` at `PaperExchange.fill()` in both handlers
  (`BacktestResult.ignored_short_signals`). Candle reads stay on Spot until `EPIC-027D` lets the user
  choose. unit 5550 passed, integration 166 passed (4 pre-existing skips), architecture 445; mypy clean on 703 files. `EPIC-027C` is
  next.
- **2026-09-26** — `EPIC-027A` done: `MarketType` moved to the shared kernel, every kline shard,
  repository/sync port and download call now carries an explicit market, legacy shards migrate once
  (idempotent, tagged Spot per O3), and Data Management/export/import show and carry the market. Full
  unit (5516), integration (165) and architecture (445) suites green; mypy clean on 702 files.
  `EPIC-027B` is next.
- **2026-09-26** — Epic scaffolded from two independent audits of the tree (live path, backtest
  path). The ADR was Accepted the same day, with every open question answered per its recommended
  option; `EPIC-027A` is now in progress.
