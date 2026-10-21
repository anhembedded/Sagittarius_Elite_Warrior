# ADR — A strategy bot is a second `IBotKind`, built backtest-first in five slices, Testnet-only until the owner says otherwise

**Epic:** [EPIC-040](README.md) · child [EPIC-040G](incomplete/EPIC-040G_strategy_bot_kind.md)
**Date:** 2026-10-20
**Status:** Proposed — parked by the owner 2026-10-20
**Decided by:** Pending the owner, who parked the epic on 2026-10-20 (*"Epic này để đó, chưa cần làm"*, leave it, no need to do it yet) without answering O1–O4; they stay open for when it is taken up. Nothing here is a default under `ONBOARDING.md` §7: the kind places real orders, so every decision below waits for the owner (the coordinator relays it).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | read on the code tree at `cf840163` (master after `EPIC-040F`); cited by path and symbol |
| 🔵 Proposed | an option with the author's recommendation; not accepted |
| ❓ Open | blocks the named slice until answered |

## 1. Context
`EPIC-040G` adds a bot that runs a strategy as a kind of its own on the shared bot shell (owner, 2026-10-14). The child file's four points to settle at start (the strategy reference, where warm-up history comes from, the position executor's scope, fault isolation) are answered below, against what the tree holds now.

✅ **What exists**
- The kind seam. `bots/contracts/i_bot_kind.py` → `IBotKind` has five abstract members (`kind_id`, `supported_profiles`, `validate`, `overlay`, `executor_factory`) and three with defaults (`parameter_problem`, `recovery_layer`, `backtester`). `bots/domain/grid/grid_kind.py` → `GridKind` is the one implementation, registered in `bots/composition/executor_bindings.py` → `_build_kind_catalog`. The executor contract is `bots/contracts/i_bot_executor.py` → `IBotExecutorFactory.create(bot) -> IBotExecutor` (`start`, `pause`, `resume`, `stop`, `confirm_resume`, …, `facts`).
- The strategy code. `strategy/contracts/i_strategy_engine.py` → `IStrategyEngine.on_tick(closed_candle, position_side) -> Signal | None` and `on_forming_bar_tick`; `IStrategyEngineFactory.build(key, params)`. Six strategies are registered by key in `strategy/composition/state_bindings.py`.
- A backtest of strategies. `backtesting/application/run_static_backtest/handler.py` → `RunStaticBacktestCommandHandler` drives `IStrategyEngineFactory.build(...)` over `backtesting/domain/paper_exchange.py` → `PaperExchange`. It is the backtesting module's own command with its own report types, not a port the bots module can call.
- The live strategy path. `strategy/application/services/live_strategy_session.py` → `LiveStrategySession.dispatch_tick` feeds closed candles to the engine. Neither it nor `MarketTickEventHandler` catches an exception from `engine.on_tick`; `LiveTradingCoordinator` catches order errors only.

✅ **What is missing, and costs work before a second kind can exist**
- The shell is typed to the Grid, not to a kind. `bots/application/services/lifecycle/bot_executors.py` → `BotExecutors` is typed to `GridExecutorFactory` and `GridExecutor`; `BotRunState` is typed to `GridRuntime` and `GridReason`; the runner's `GridStartPreconditions` is built in `_build_executing_runner`. `tests/unit/architecture/baseline_bots_shell_imports_a_kind.txt` is the shrink-only list of shell files that already import a kind. `EPIC-029B` said the seam makes a second kind a registration; it is not yet true of the executor path.
- A strategy declares no version and no warm-up. `BaseStrategy` has parameters and `supported_directions`; warm-up is implicit (indicators answer `None` until primed).
- `bots` imports nothing from `strategy`. `BotsModule.dependencies` is `["trading", "market_data"]` (`bots/module.py`); `test_module_declarations.py` fails on a surplus or a shortfall.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **Five slices, backtest first.** G1 makes the shell kind-neutral (no behaviour change; `BotExecutors`, `BotRunState`, the start preconditions take an `IBotKind`'s executor, and the baseline file shrinks). G2 gives strategies a declared spec (D2, D3) in the strategy module. G3 is the strategy kind's `IKindBacktester` on the workbench: no order is ever placed. G4 is the executor and the kind's lifecycle, Testnet only (D8). G5 migrates saved armed-strategy configs into stopped strategy bots. One pull request each, a reviewer each. | 🔵 Proposed | Pending the owner | The owner can backtest every strategy on the workbench after G3 with no order path built. G1 and G2 touch the shell and the strategy module and carry the regression risk; they come first so nothing later changes them. Five PRs instead of one 🔴 PR. |
| D2 | **The strategy reference is an id plus a declared integer version.** A strategy class declares `VERSION` (bump it when its decisions change). The bot's plan holds `strategy_id` and `strategy_version`; Start refuses when the host's version differs ("this host runs version 3, the plan names 2"). A content hash is not used. | 🔵 Proposed | Pending | A server runs the code that was backtested, readable in the plan file. A hash changes on formatting and no person can read it; it can be added to the provenance later without changing the plan. The cost is a person must remember to bump the number; a test per strategy pins the behaviour of the current version on a fixed candle series, so a change without a bump goes red. |
| D3 | **Warm-up is declared, through a new small port.** `IStrategyCatalog.describe(key) -> StrategySpec(version, warmup_candles, supported_directions, parameters)` in `strategy/contracts/`, read by the bots module. `warmup_candles` is a declared `ClassVar` on the strategy, not derived by running it. | 🔵 Proposed | Pending | Adding a method to `IStrategyEngineFactory` would change every implementer (`BUG-026`); a new port is the seam. The declared number is checked by a test that feeds exactly that many candles and requires the first signal-capable state. |
| D4 | **History comes through a bots-side port over `market_data`'s contracts.** `IWarmupCandles.closed_candles(symbol, interval, count, before)` answers stored closed candles; the live executor and the backtester both read it. The bot never fetches history itself. | 🔵 Proposed | Pending | One reader for both paths is what makes the parity test meaningful. It reuses the stored-candle reader the Grid's backtest already uses (`StoredKlinesReader`). |
| D5 | **First executor slice: one position per bot, no trailing, no re-entry.** Enter at the market after a closed bar's signal, with the plan's stop loss and take profit (percent) placed through the shell's gateway; Spot long only; Futures long and short per the venue profile, no reversal (reversal needs the `039L` protective stop first). Every order goes through `BotOrderGateway`, the order pacer, the exposure book and the risk guard as the Grid's do. | 🔵 Proposed | Pending | The smallest thing that is a real strategy bot and reuses every guard. Trailing stops and re-entry are variants behind the same plan keys (seam now, variant later). |
| D6 | **A strategy fault halts that bot, never the host.** Every call into `IStrategyEngine` runs inside one boundary that catches `Exception`, logs the strategy, its version and the error, and halts that bot (`HALTED`, reason `strategy_fault`) through the shell's halt path. No per-call time budget in the first slice. | 🔵 Proposed | Pending | Today an exception from `engine.on_tick` is uncaught on the live path; the boundary is new code with its own test (a raising strategy halts one bot and leaves a second running). Price paid, recorded as a test that pins it: a strategy that hangs blocks that bot's own work queue (`IBotWorkQueue` is one thread per bot) and nothing else; a watchdog is the later fix. |
| D7 | **No trade record on the outcome.** The strategy kind pairs its own entries and exits into its `figures` (trades, win rate, average holding time) and keeps the pairs in `detail`; `BacktestOutcome` and the workbench do not change. | 🔵 Proposed | Pending | `040B`'s review left this open. A neutral trade record is a second contract change for one kind (seam now, variant later); pairing fills is a few functions the kind owns. |
| D8 | **The kind is Testnet-only until the owner lifts it.** `StrategyKind.validate` refuses Start on a mainnet venue ("strategy bots run on Testnet until EPIC-040G's Testnet run is recorded"). | 🔵 Proposed | Pending | No real-money path opens by this epic alone. Lifting it is a one-line change the owner decides, after a recorded Testnet run (the child's §5 already requires one). |
| D9 | **Parity is by construction and by test.** The backtester calls `IStrategyEngineFactory` directly with the same candle reader as the live path (D4), not `RunStaticBacktestCommandHandler` (its own types, its own sizing). A signal on a closed bar is acted on at the next bar's open, in both paths. Mandatory tests: the same closed candles through both paths give the same signals in the same order for each strategy; a closed-bar strategy never sees the next candle; nothing before `start` is traded. | 🔵 Proposed | Pending | Wrapping the backtesting module's handler would give a second simulator of the same strategies, which is the drift the epic removes. The cost is a small paper-position model in the kind's backtester; the Grid's own simulator is the precedent. |
| D10 | **The module dependency is declared, contracts only.** `BotsModule.dependencies` gains `"strategy"`; `bots` imports only `strategy/contracts/`. | 🔵 Proposed | Pending | One declaration line the guards require; no allowlist entry. |
| D11 | **The Strategies panel keeps working unchanged until G5.** Arming from the Desk and the per-venue armed-strategy store (`LiveStrategyConfigStore`) are not touched before the migration. **Superseded for the Bots screen by [BOT-219](../../completed/BOT-219_the_strategies_dock_is_removed_from_the_bots_mode.md) (the owner, 2026-10-21, option A): the panel is gone; Arm strategy… and Disarm strategy… ask which venue; the armed-strategy store is untouched.** | 🔵 Proposed | Pending | No behaviour change for anyone arming a strategy today. G5's migration is idempotent and logged; it creates stopped bots and does not disarm anything. |

## 3. Alternatives considered
- **One pull request for all of `040G`.** Rejected: shell generalisation, a new port, a backtester and an order-placing executor in one 🔴 review is the shape that hides a defect; the slices each have a test that stands alone.
- **Executor first, backtest later.** Rejected: the backtest is the part with no order path, and the parity tests it needs are what the executor is then built against (P4).
- **Wrap `RunStaticBacktestCommandHandler` as the backtester.** Rejected: see D9.
- **A content hash as the strategy version.** Rejected: see D2.
- **A Grid subclass that loads a strategy.** Already rejected in the child file (no shared execution logic).

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Does the owner accept the five slices in this order (D1), in particular a first PR that changes the shell with no visible change? | G1 | 2026-10-20 |
| O2 | Testnet-only until a recorded Testnet run, then lifted by the owner (D8)? | G4 | 2026-10-20 |
| O3 | Are all six existing strategies in scope for the first slice, or only `ema_crossover` with the other five after their versions and warm-ups are declared and pinned? Recommendation: all six are declared in G2 (it is a spec per class), but G4's first Testnet run uses `ema_crossover` only. | G2 | 2026-10-20 |
| O4 | Is "no trailing stop and no re-entry in the first slice" (D5) what the owner expects of a first strategy bot? | G4 | 2026-10-20 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D11 | [EPIC-040G](incomplete/EPIC-040G_strategy_bot_kind.md) | Not started | Not yet verified: this record is the design, written before any code. |
