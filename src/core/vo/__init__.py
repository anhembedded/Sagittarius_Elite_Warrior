"""The Published Language: value objects every module may read, owned by none.

**Not a Shared Kernel.** In this repository `architecture-rule.md` §3 defines the
Shared Kernel as exactly two Engine symbols, and a test locks that definition.
This package is Evans' *Published Language*: types that are immutable, neutral
with respect to any one context's business language, and readable everywhere.

**Admission rule** (HLD §2.4): a type enters only once it already has at least
two consumers in at least two different modules — measured, never guessed. The
two founding members were measured on 2026-09-14:

| Type | Importers in `src/` | Contexts that read it |
| :--- | :-: | :--- |
| `MarketData` (one OHLCV candle) | 43 | market_data, backtesting, strategy, indicators, trading, the dev board |
| `TimeFrame` | 53 | the same six, plus the CLI and the timeframe picker |

Both are stdlib-only — a frozen dataclass and an enum — so nothing here imports
a module, a support package, the legacy tree, or a UI toolkit. `MarketData` is a
candidate for renaming to `Candle` later; a rename storm is not a pure refactor,
so it keeps its name for now (HLD §2.4).
"""
