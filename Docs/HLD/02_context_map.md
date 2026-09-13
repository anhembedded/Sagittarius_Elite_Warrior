# §2 — Context map

- **Diagrams (component, PlantUML) — high view first, detail second:**
  [`hld-01a_layer_map.puml`](diagrams/hld-01a_layer_map.puml) — the five layers and the
  direction of every dependency;
  [`hld-01b_module_dependencies.puml`](diagrams/hld-01b_module_dependencies.puml) — every module
  pair, the ports that cross it, and the integration pattern of §2.3.

## 2.1 The map

```
                 ┌──────────────────────────── shell/ (Martin's "Main") ────────────────────────────┐
                 │  explicit module list · surfaces: trading / dev_board / settings · CLI          │
                 └───────────────────────────────────────────────────────────────────────────────────┘
                                                      │ knows only IExtension + contracts/
   ┌──────────────┐    IHistoricalKlines     ┌──────────────┐   IOrderSubmission    ┌──────────────┐
   │ market_data  │ ───────────────────────▶ │  strategy    │ ────────────────────▶ │   trading    │
   │ (Supporting) │    MarketTickEvent       │  (CORE)      │   ITradingSession     │ (Supporting) │
   └──────────────┘                          └──────────────┘   .claim_symbol()     └──────────────┘
          │  IHistoricalKlines                      ▲  IStrategyCatalog · ISizingPolicy     │
          │  IMarketDataSync · IRangeCoverage       │  IStrategyEngineFactory                │ (depends on no
          ▼                                         │                                        │  business module)
   ┌──────────────┐ ────────────────────────────────┘
   │ backtesting  │  (Supporting) — ACL: PaperExchange ⇄ StrategyContext
   └──────────────┘

   support/ (Generic):  binance_gateway · charting · indicators · ui_kit      core/: contracts · vo (Published Language)
   kernel (Engine):     DI · bus · config · log · thread · scheduler · hosted · (navigation — Phase 5)
```

An arrow is a **dependency direction**: A → B means A imports `modules/B/contracts/`. There are no
reverse arrows and no cycles; the guard `test_module_boundaries.py` (§6) locks this in.

## 2.2 Distillation — what is the core

Distillation is Evans' name for asking which part of the domain is the reason the system exists,
so that design effort goes where it matters.

| Kind | Module | Why |
| :--- | :--- | :--- |
| **Core domain** | `strategy` | The reason the app exists: turning a trading idea into a signal. It is where the user changes things most often and most creatively. Every other module exists to **feed** it (market_data), **execute** it (trading) or **verify** it (backtesting) |
| **Supporting** | `market_data`, `trading`, `backtesting` | Necessary, with business meaning of their own, but replaceable (another exchange, another simulator) without the app ceasing to be this app |
| **Generic** | `support/{binance_gateway, charting, indicators, ui_kit}` | Purely technical; in principle something one could buy or download |

The practical consequence: **quality investment** (tests, review, design time) goes to `strategy`
first, then `trading`, then the rest. *Core* means "the reason the app exists", **not** "the largest
or hardest module": `strategy`'s own state is thin (one `LiveStrategyConfig` in a single-slot
`LiveStrategySession`), while `trading` carries the highest operational risk — it is the module
that can lose real money on Testnet — and gets the same review budget. And `strategy` must **never** depend on exchange details — it
sees only `trading.contracts` and `market_data.contracts`.

## 2.3 The integration pattern for each pair

Evans catalogues the ways two contexts can relate. Naming the pattern for each pair tells the
reader what to expect at the boundary before opening the code.

| Pair (upstream → downstream) | Pattern | Concretely |
| :--- | :--- | :--- |
| `market_data` → `strategy`, `trading`, `backtesting` | **Open Host Service + Published Language** | `IHistoricalKlines`, `IMarketStream`, `IMarketDataSync`, `IRangeCoverage`; the shared language is `core/vo` (`MarketData`, `TimeFrame`) and `MarketTickEvent` |
| `trading` → `strategy` | **Customer/Supplier** — `trading` supplies, `strategy` consumes | `IOrderSubmission`, `ITradingSession`, `IAccountSnapshot`. `trading` **does not know** that `strategy` exists |
| `strategy` → `backtesting` | **Customer/Supplier** — `strategy` supplies | `IStrategyCatalog`, `IStrategyEngineFactory`, `ISizingPolicy` (ADR D17). `backtesting` **runs** strategies and sizes with the same rule; a strategy does not know it is being backtested |
| `backtesting` ⇄ `PaperExchange` versus `StrategyContext` | **Anticorruption Layer** inside `backtesting` | `strategy` defines its own `StrategyContext` (candles plus the current position as a neutral value object); `backtesting/adapters/` translates `PaperExchange` into it; `trading` provides one from `LivePosition`. (Round-3 correction: the earlier claim that `strategy_context.py` imports `domain/backtesting` was **false** — measured, nothing under `domain/strategies/` does. The real wrong-direction import is **`trading → backtesting`**: `domain/trading/policies/position_sizing_bridge.py:21` imports `MarginRiskPolicy` from `domain/backtesting/policies/`. That is a dependency §2.1 forbids, drawn on no diagram. **Decided — ADR D17:** sizing belongs to `strategy`; `MarginRiskPolicy` and the bridge move there in Phase 2 behind `ISizingPolicy`, which both `trading`'s callers and `backtesting` consume.) |
| `support/binance_gateway` → `market_data`, `trading` | **Anticorruption Layer**, shared, for the SDK | Only the gateway may construct `binance.client.Client` (an existing guard test). Each context wraps **its own** part of the SDK in its own `adapters/`: `market_data/adapters/binance/` (REST klines, market websocket), `trading/adapters/binance/` (futures REST, user-data websocket) |
| `support/charting` ← every module with a chart | **Conformist** (the downstream accepts the upstream's model) | A module draws through `IChartHost` and charting's `MarkerPoint` / `RegionSpan` / `InfoField` types, without translation |

## 2.4 The Published Language — `core/vo`

**Do not call this a "Shared Kernel".** In this repository `architecture-rule.md` defines the Shared
Kernel as exactly two Engine symbols, `IDomainEvent` and `BaseEvent`, and a test locks that
definition. `core/vo` is a **Published Language**: value objects that are neutral with respect to any
business language, immutable, readable by every module and **owned by none**.

**Admission rule.** A type enters `core/vo` only when it already has at least two consumers in at
least two different modules — measured, not guessed. The rule decides *placement*, not shape: a value
object that lives inside one module today is already immutable and free of that module's
business logic, so promoting it later is a move plus an import rewrite, never a redesign
(`architecture-rule.md` §7.2.1). Guard: `core/` imports nothing from
`modules/*`, `support/*` or PySide6.

| Value object | Consumers measured on 2026-09-11 | Into `core/vo`? |
| :--- | :--- | :-: |
| `TimeFrame` | all four layers, five packages | ✅ |
| `OrderSide`, `PositionSide` | application, domain, infrastructure, presentation | ✅ |
| `MarketDataVenue`, `TradingVenue` | every layer plus the composition root | ❌ → `support/binance_gateway/contracts` (round 3): both are **closed Binance-specific enums** (`{MAINNET_PUBLIC, FUTURES_TESTNET}`, `{DISABLED, FUTURES_TESTNET}`), so a second exchange would edit the Published Language. Every module may import a support package's contracts, so nothing loses access |
| `Currency`, `MarketType` | domain and presentation | ✅ |
| `MarketData` (the OHLCV candle, `domain/entities/market_data.py`) | market_data, backtesting, strategy, indicators, charting | ✅ — renaming it `Candle` is a **candidate** for later; a rename storm is not a pure refactor |
| `PositionSizing`, `PositionSizingType` | backtesting, trading (`position_sizing_bridge`), strategy | ✅ (the value type stays neutral; the *rule* that uses it, `MarginRiskPolicy`, belongs to `strategy` — ADR D17) |
| `ExchangeCredentials`, `VenueAlignment` | kernel and settings | ❌ → `support/binance_gateway/contracts`, with the venues |
| `SignalAction`, `Signal`, `LiveStrategyConfig` | strategy only (plus trading through the bridge) | ❌ → `strategy/contracts` |
| `BrokerSimulationConfig`, `CommissionType` | backtesting only | ❌ → `backtesting/domain` |
| `ExchangeConnectionStatus`, `PositionMode`, `MarginType` | trading and settings | ❌ → `trading/contracts` (the settings section is contributed by trading) |
| `Symbol` | **does not exist** — a symbol is a raw `str` everywhere | ❌ not invented in this epic; recorded as a candidate |

## 2.5 Events that cross a boundary — measured publishers and subscribers

Only an event declared in `contracts/` exists for the outside world. The table below is the
**complete** list of cross-module events after the split; anything not listed is internal to its
module.

| Event | Publisher (module) | Subscribers outside the module | Note |
| :--- | :--- | :--- | :--- |
| `MarketTickEvent` | `market_data` (market websocket) | `strategy` (tick → engine), `trading` (live chart), surfaces | ✅ already a bus event |
| `SingleSyncProgressEvent` | `market_data` | `backtesting` (data sync), surfaces | ✅ |
| `SignalGeneratedEvent` | `strategy` | `backtesting` (log and markers), surfaces (the "last signal" card) | ✅ — `LiveTradingCoordinator` consumes it **in-process**, not over the bus; that stays internal to `strategy` |
| `LiveOrderBlockedEvent` | `strategy` (`LiveTradingCoordinator` moves to strategy: it is "the decision not to send an order") | surfaces | ⚠️ today it lives in `application/services/` with no owner |
| `OrderFilledEvent`, `PositionChangedEvent`, `PositionClosedEvent`, `EquitySampledEvent` | `trading` | `charting` (fill markers, through trading's adapter), surfaces | ✅ |
| `TradingSessionChangedEvent` 🔵 | `trading` | surfaces (replacing three Presenters that read `TradingSessionState` directly) | new — a change of **mechanism**, not of business behaviour |
| `StrategyArmedEvent` / `StrategyDisarmedEvent` 🔵 | `strategy` | surfaces | new — replacing `LiveStrategySession` being read directly by two Presenters |
| `BacktestCompletedEvent`, `BacktestFailedEvent` | `backtesting` | — | **internal** (only the backtest screen listens) |
| `OrderSubmittedEvent`, `OrderRejectedEvent` | **nobody** | **nobody** | dead — deleted in Phase 1 |
| `BulkSyncProgressEvent` | `market_data` | — | internal |

Each cross-module event has **exactly one** normalising Feed in the owning module
(`architecture-rule.md` §6); a surface only *displays* it through the widget the module contributes.
