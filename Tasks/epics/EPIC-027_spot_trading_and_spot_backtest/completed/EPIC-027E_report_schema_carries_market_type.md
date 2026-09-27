# EPIC-027E — A saved backtest report states which market it simulated

**Status:** ✅ Done (2026-09-27)
**Source:** follows the user's *"back test theo spot"* request, 2026-09-26.
**Risk:** 🟢 — additive schema change with a default; old reports must still load.
**Complexity:** S — one config field, the ignored/rejected counters, a schema version bump.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027B](../completed/EPIC-027B_spot_mode_in_the_backtest_engine.md), [EPIC-027C](../completed/EPIC-027C_exchange_filters_on_simulated_fills.md)

---

## 1. Context and problem
- Report schema v1 serializes `long_leverage`/`short_leverage` and each trade's side and leverage
  (`src/modules/backtesting/.../backtest_report_serializer.py:82-83,135-136`). The loader requires
  those fields (`backtest_report_loader.py:202-203,280-281`).
- Nothing records the market, so a Spot report and a Futures report of the same symbol cannot be
  told apart. That undermines the side-by-side comparison (`BOT-115D`).
- Since `EPIC-027B`–`027D` the facts exist on the result, but not in the report:
  - `BacktestResult` carries `market_type`, `ignored_short_signals`, `rejected_entries` and
    `exchange_filters`.
  - `BrokerSimulationConfig` carries `market_type` and `exchange_filters`.
  - The serializer writes none of them. The loader rebuilds a result with their defaults, so a
    loaded report reads as a Futures run with no filters: the default, not the fact. This task
    makes that "not recorded (pre-EPIC-027)".

## 2. Acceptance criteria
- [x] A new report carries `market_type`, the ignored-short count and the exchange-filter provenance.
- [x] A v1 report still loads. Its market is shown as "not recorded (pre-EPIC-027)", not guessed.
- [x] The comparison dialog warns when the two reports simulate different markets.

## 3. Design
- A schema version bump (1 → 2) with every new field defaulted on load, following the precedent of
  `BOT-115A`'s versioning. `MIN_SUPPORTED_SCHEMA_VERSION` is introduced alongside `SCHEMA_VERSION` so
  the loader can accept a version range (`[MIN, SCHEMA_VERSION]`) instead of only exact equality —
  the first time this codebase has had more than one schema version to accept.
- Each new field's default on load is that field's own dataclass default (`BacktestResult`'s
  `market_type=FUTURES_USD_M`, `BrokerSimulationConfig`'s `exchange_filters=None`, etc.) — a v1 file
  re-runs and re-computes exactly as it did before this task, byte for byte.
- "Not recorded" is a fact about the *load*, not a value `BacktestResult` can hold — a `MarketType`
  field cannot itself mean "unknown" without inventing a fourth enum member nothing else should ever
  see. So it lives on `BacktestReportLoadResult.market_type_recorded: bool`, the same place
  `strategy_key_unknown`/`metrics_mismatch` already live for the identical reason (a fact about
  *this load*, not about the report's own schema). `market_type_recorded` is derived from whether the
  JSON payload's `result` object actually contains a `market_type` key — not from `schema_version`
  alone — so a hand-edited v1 file that happens to carry the new keys is still read correctly.
- `build_report_provenance_warning_text()` grew a fourth flag to check
  (`market_type_recorded`). Rather than a fourth boolean parameter (`code/quality.md` §7's own
  4-argument ceiling — the function was already at 4 with `report` + 3 flags + 1 keyword), it now
  takes the whole `BacktestReportLoadResult` in place of the three individual `bool` flags it used to
  unpack manually. Every call site (one in `backtest_presenter.py`, five in its own test file) already
  had a `BacktestReportLoadResult` in scope, so this is a strict simplification, not new plumbing.
- The market-mismatch warning is a **new**, separate function
  (`build_market_type_mismatch_warning`), not folded into the existing `build_market_mismatch_warning`
  — that one already overloads the word "market" for the *trading pair* (its docstring literally says
  "Comparing different markets: BTCUSDT vs ETHUSDT"), predating this epic's `MarketType` (Spot/
  Futures) vocabulary. Renaming the older function to remove the collision would touch call sites and
  tests outside this task's bounds, so both warnings compose side by side in the dialog, joined by the
  same `"   •   "` separator the rest of this screen already uses for multi-note warnings.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/contracts/backtest_report.py` | `SCHEMA_VERSION` 1→2, new `MIN_SUPPORTED_SCHEMA_VERSION`, `BacktestReportLoadResult.market_type_recorded` |
| `src/modules/backtesting/contracts/backtest_report_serializer.py` | writes `market_type`/`exchange_filters`/`ignored_short_signals`/`rejected_entries` on the result, and `market_type`/`exchange_filters`/`break_even_trigger_pct`/`trailing_activation_pct`/`trailing_offset_pct`/`partial_take_profit_levels` on `broker_config` |
| `src/modules/backtesting/contracts/backtest_report_loader.py` | accepts `[MIN_SUPPORTED_SCHEMA_VERSION, SCHEMA_VERSION]`; reads every new field with its own dataclass default when absent; derives `market_type_recorded` from key presence |
| `src/modules/backtesting/ui/logic/report_comparison_rules.py` | new `build_market_type_mismatch_warning()` |
| `src/modules/backtesting/ui/backtest_modals/report_comparison_dialog.py` | composes both mismatch warnings |
| `src/modules/backtesting/ui/logic/report_import.py` | `build_report_provenance_warning_text()` takes `loaded: BacktestReportLoadResult` instead of two `bool`s; new "not recorded" note |
| `src/modules/backtesting/ui/backtest_presenter.py` | updated call site |
| Tests (see §5) | round-trip, v1 back-compat, mismatch warning, provenance warning |

## 5. Testing
- **Unit, new/extended:**
  - `contracts/test_backtest_report.py`: the round-trip spine test now asserts `market_type`,
    `ignored_short_signals`, `rejected_entries`, `exchange_filters` and `loaded.market_type_recorded`
    survive export → import; a dedicated Spot-only report round-trips
    `break_even_trigger_pct`/`trailing_activation_pct`/`trailing_offset_pct`/
    `partial_take_profit_levels` (kept out of the shared fixture — it already sets
    `take_profit_pct`, mutually exclusive with a scale-out ladder); a new test strips every
    EPIC-027E key from a real v2 payload down to exactly what `schema_version` 1 ever wrote and
    asserts it still loads, with `market_type_recorded is False` and every new field at its
    default.
  - `ui/logic/test_report_comparison_rules.py`: `build_market_type_mismatch_warning` — same market
    has no warning, Spot vs Futures names both, and a symbol-only change does not also trip it
    (the two warnings are independent axes).
  - `ui/logic/test_report_import.py`: the five existing `build_report_provenance_warning_text` tests
    updated to the new `loaded`-based signature; one new test for the "not recorded" note; the
    multi-note separator count test bumped from 2 to 3.
  - `ui/test_report_comparison_dialog.py`: unaffected — its one warning-label assertion checks the
    pre-existing symbol-mismatch text, which the new composition still produces unchanged when
    markets agree.
- **Mutation:** removing `"market_type": result.market_type.value,` from the serializer (confirmed by
  temporarily reverting the file) turns the round-trip spine test, the Spot-fields round-trip test and
  the v1-compat test red for the right reason (`KeyError`/wrong-field assertions), then green again on
  restore.
- **Suites:** 5618 unit passed. 168 integration passed (4 skipped). 32 sanity passed. Architecture 445 passed. `ruff`/`ruff format`/`mypy` clean on the whole tree; `tests/unit/modules/backtesting` (1072 tests, this task's own module) green.

## Implementation notes (written when done)
- **Root cause was literal data loss, not a design gap.** `BacktestResult`/`BrokerSimulationConfig`
  already carried every fact `EPIC-027B`/`027C` added; the serializer simply never wrote four of
  them (plus four pre-existing `BOT-105A`/`105C` fields nobody had noticed either — see this task's
  own "Notes" section, folded into the same v2 bump since it stayed Complexity S).
- **"Not recorded" is now a first-class, non-guessable state**, surfaced through the same
  `BacktestReportLoadResult` flag mechanism `BOT-078` already established for `strategy_key_unknown`/
  `metrics_mismatch`, rather than inventing a new sentinel on `MarketType` or `BacktestResult` itself.
- **The market-type mismatch warning is deliberately a sibling function, not a rename.** The existing
  `build_market_mismatch_warning`'s use of the word "market" for the trading pair predates this
  epic and is now a real naming collision (`code/naming.md` §4: one vocabulary per concept) — flagged
  here rather than silently fixed, since renaming touches call sites this task does not otherwise
  need to change.
- **`build_report_provenance_warning_text` shrank from 5 parameters to 3** by accepting the
  `BacktestReportLoadResult` it always had in scope instead of three separately-unpacked booleans —
  a byproduct of staying under `code/quality.md` §7's 4-argument ceiling once a fourth flag was
  needed, not a planned refactor.
