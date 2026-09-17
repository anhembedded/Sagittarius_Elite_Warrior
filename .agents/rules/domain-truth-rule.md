---
name: Domain Truthfulness Rule
description: The system never lies about what it did — real coverage, real exchange filters, immutable snapshots, distinct trading facts, a UI that promises only what the engine delivers.
trigger: on_file_change
patterns:
  - src/domain/**/*.py
  - src/application/**/*.py
  - src/modules/*/domain/**/*.py
  - src/modules/*/application/**/*.py
---

# Truthful data

A number valid as a type can still lie about the business, and here that is real money.

- **Coverage** is proven by internal gaps at the timeframe cadence on normalised UTC boundaries, never by min/max or row count. `[review: F1]`
- **Exchange rules** (min notional, lot size, tick size, leverage) come from cached metadata for the active symbol; never account capital as notional, never a universal hard-coded filter. `[review: F1]`
- **Snapshots** are immutable, memory-bounded and carry provenance: configuration, data window/watermark, strategy version and parameters, fee model, execution mode. `[review: F4]`
- **Business contract before implementation contract.** A test first states the observable business promise (inputs, order and position transitions, fills, side, PnL direction, visible table/chart), then the implementation. Green on private calls is not evidence. `[review: E2]`
- **Distinct trading facts.** Signal, order intent, fill, position entry, position exit and short entry are separate facts; an ambiguous `BUY`/`SELL` never stands for two of them. In a long-only engine `SELL` is an exit, not a short. `[review: F2]`
- **Truthful UI.** Every label, marker, filter, metric and empty state describes what happened and what the engine supports now; an unsupported capability is hidden, disabled or labelled unavailable. Test the displayed semantics, not only the payload. `[review: F3]`
- **No latency claims** without a reproducible benchmark (workload, cache condition, method); ETA is an estimate. A renderer comparison drives the same payload, input sequence and visual grab through both implementations and reports median/p95, DPR, backend and warnings; never improve a number by dropping markers or a final render check. `[review: F5]`
- **Backtest chart host** stays behind the narrow `IBacktestChartHost` protocol and a transient factory; view-owned, never a singleton or hot-swapped.
- **Counterintuitive story check.** When a story, label or default can conflict with a TradingView-style mental model, report the observable behaviour and trade-off before finalising; encode the chosen semantics in copy and acceptance tests. `[eye]`
