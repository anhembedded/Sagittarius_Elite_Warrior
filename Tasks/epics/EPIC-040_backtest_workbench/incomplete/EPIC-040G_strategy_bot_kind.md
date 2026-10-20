# EPIC-040G — A bot that runs a strategy is its own kind on the shared shell, backtested on the workbench with the same strategy code it runs live

**Status:** 🔵 Backlog — after `040F`; the per-file design is written when it starts, against the tree as it is then
**Source:** The owner, 2026-10-14: *"Bot theo strategy bạn nghĩ nó có nên là 1 loại bot riêng ko (loại bot này chuyển load strategy, tui nghĩ nó sẽ có nhiều cái thao tác xử lý phức tạp hơn grid bot và các bot nổi tiếng). nó cũng base vs bot grid"* (should a strategy bot be a kind of its own? It loads a strategy and will need more complex handling than the Grid and the well-known bots; it is also based on the Grid bot). Then: *"gộp ý vừa rồi vào epic tách bot common"* (merge that into the epic that makes bots common).
**Risk:** 🔴 — real orders driven by strategy code; a backtest that differs from live, or a strategy fault that takes the host down, costs money
**Complexity:** L — a second `IBotKind`, a position executor, warm-up and recovery, a backtester adapter, migration of saved strategy configs
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040B](../completed/EPIC-040B_kind_neutral_backtest_contract.md) (the port this kind's backtest answers through), [EPIC-040F](EPIC-040F_grid_on_the_workbench.md) (the workbench proven on the Grid first)

---

## 1. Context and problem
- Today a strategy is armed on a venue from the Strategies panel (`ui/strategies/`), not run as a bot. Its symbol is the chart's, it has no bot lifecycle, it is not in a plan file (`BOT-176`), and the headless host cannot run it.
- The strategy code itself already exists behind published ports: `IStrategyEngine` / `IStrategyEngineFactory` (`modules/strategy/contracts/i_strategy_engine.py:54,87`), with six strategies under `modules/strategy/domain/strategies/`.
- `EPIC-029L` planned a `SignalKind` together with a DCA kind, last in line. The owner now wants the strategy bot designed as part of making bots common. The signal half of `029L` moves here; DCA stays in `029L`.

## 2. Acceptance criteria
- [ ] A strategy kind implements `IBotKind` (`validate`, `overlay`, `executor_factory`) and registers in the kind catalog. Nothing kind-neutral changes beyond that registration, and it names no Grid type.
- [ ] A strategy bot has an explicit symbol, interval, strategy id and strategy version, and the shell's lifecycle (Start, Pause, Resume, Stop, restart recovery). It exports to and applies from a plan file like any bot.
- [ ] **Same code, same signals.** Backtest and live call the same strategy through the same `IStrategyEngine`. A parity test feeds the same closed candles to both paths and gets the same signals in the same order.
- [ ] **No lookahead.** A signal is acted on only after its candle closes, unless the strategy declares forming-bar decisions (`on_forming_bar_tick`). A test proves a closed-bar strategy never sees the next candle.
- [ ] **Warm-up.** Before the first signal, the bot loads the history the strategy says it needs, both at Start and after a restart. Until warm-up completes, the bot says it is warming up and places no order.
- [ ] **Strategy faults are contained.** An exception from strategy code halts that bot (HALTED, with the strategy and the error in the log) and never stops the host or another bot.
- [ ] **One position, managed by the shell's guards.** Entry, stop loss, take profit and exit go through the venue profile, risk guard, exposure book and order pacer that the Grid uses. Spot runs long only; Futures directions follow the venue profile.
- [ ] The kind's `IKindBacktester` adapter runs on the `040D` workbench and reports position trades and the kind's figures.
- [ ] The saved per-venue strategy configs are migrated once into stopped strategy bots. The migration is idempotent and logged.

## 3. Design
**A kind of its own, not a Grid subclass.** The Grid is a ladder of resting orders; a strategy bot turns closed candles into signals and manages one position. Inheriting from the Grid would carry ladder state the strategy never uses. The shared parts already sit below both kinds in the bot shell. P5: the kind seam (`EPIC-029B`, ADR D2) exists for exactly this.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Own kind on the shared shell (chosen) | One new kind and one registration; every shell guard applies unchanged |
| A Grid variant that loads a strategy | Rejected: no shared execution logic, and the ladder's state would mislead recovery and the risk guard |
| Keep desk arming and add a lifecycle to it | Rejected: a second lifecycle beside the bot shell, invisible to the host and to plan files |

**Points the per-file design must settle when this task starts:**
1. **The strategy reference in a plan.** It must name the strategy id and a version, so a server runs the code that was backtested. Whether the version is a declared number or a content hash is decided then.
2. **Where warm-up history comes from.** It comes from the market-data module through its published port, both live and in the backtest. The bot never fetches history directly.
3. **Position executor scope.** It is one position per bot. Whether trailing stops and re-entry are in the first slice is decided then; reversal on Futures needs the 039L protective stop first.
4. **What fault isolation runs.** Strategy calls run inside a boundary that catches, logs and halts. Whether strategy code also gets a time budget per call is decided then.

**From `040B` (review of PR #627).** The outcome reports entries and exits as labelled `fills`; it has no trade record (entry, exit, profit, holding time). Decide here whether the kind adds one beside `fills` or the workbench pairs the fills. The stub adapter of `040B` cannot test that nothing before `start` is reported (warm-up is replayed but never traded): the parity suite of this task carries that assertion.

## 3a. Reuse
To be filled when the task starts. Expected uses: `IBotKind`, `IBotKindCatalog`, `IStrategyEngineFactory`, the venue profile, `IRiskGuard`, `IExposureBook`, `IOrderPacer`, the plan document, and `040B`'s `IKindBacktester`.

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts. Each criterion above maps to a unit or integration test. The parity and no-lookahead tests are mandatory. A Testnet run is needed before any mainnet use.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
