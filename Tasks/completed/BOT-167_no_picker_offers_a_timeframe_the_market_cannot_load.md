# BOT-167 — No picker offers a timeframe the selected market cannot load: `1s` is hidden wherever Futures is the market

**Status:** ✅ Done (2026-10-07)
**Board:** Decision: the intervals a market loads are one domain fact, `core/vo/market_timeframes.py` (Spot all sixteen, Futures none of `1s`), asked by the chart toolbar, the Backtest timeframe field and the Data mode's sync list; a switch to Futures while `1s` is selected falls back to `1m` and logs it. Does not fix `BUG-166` (a)–(c).
**Source:** The owner, 2026-10-07, through the coordinating session (session_01PZn6EWxn6gytSGKwbuRJGg): hide `1s` wherever Futures is the market, with the rule in one place; evidence: Binance USD-M has no 1s klines (`BUG-166`).
**Risk:** 🟡 — touches the shared chart toolbar and three screens; a wrong rule would hide a timeframe a market does load
**Complexity:** M — one rule, three consumers, two baseline-bound files
**Depends on:** None (`BUG-166` records the evidence)

---

## 1. Context and problem
Binance USD-M Futures answers `-1120 Invalid interval` for `fapi/v1/klines?interval=1s`; Spot has complete 1s klines. Every timeframe list derived from `TimeFrame` (the chart toolbar through `all_options()`, the Backtest `timeframeOptions`, the Data mode's `_SUPPORTED_INTERVALS`) offered `1s` regardless of the market, so a user could pick a timeframe the market cannot load. Survey (`grep -rn ONE_SECOND src`): the only code that names `ONE_SECOND` outside the enum are the Backtest's fixed tick resolution (`backtest_fsm_matrix.py:301`, `backtest_report.py:119`, not a picker) and the grid backtest's own 1s read (Spot bots); there is no tick-resolution picker. The three lists above are the pickers.

## 2. Acceptance criteria
- [x] One rule says which timeframes a market loads: `1s` is not loadable on Futures, everything is on Spot.
- [x] While the market is Futures, `1s` is absent from the chart's timeframe bar (pills and the picker's grid) in Market mode, the Backtest screen and the Desk's Futures chart.
- [x] While the market is Futures, `1s` is absent from the Backtest's timeframe field; on Spot it is present again.
- [x] The Data mode's sync interval list is the rule's list for the market its syncs fetch (Spot today), so no Futures 1s sync can be started.
- [x] Switching market while `1s` is selected falls back to `1m` (Backtest field and chart; a Market-mode chart opens on `1m` when its default is `1s` and the market is Futures), and each fallback is logged.
- [x] Tests written first, mutation-checked; no file crosses or grows past the 400-line ceiling; `engine.ref`, `requirements*`, `pyproject.toml`, `.claude/settings.json` untouched.

## 3. Design
The rule is a domain fact in `core/vo/market_timeframes.py`: `timeframes_for(market)`, `supports_timeframe(market, code)`, `timeframe_or_fallback(market, code)`. Fallback is the shortest supported timeframe not shorter than the one asked for (`1s` → `1m`). `FUTURES_COIN_M` shares the Futures list per Binance's documented kline intervals; it was not probed and nothing offers it yet. A `MarketType` member with no entry fails `test_every_market_declares_a_rule`.

Consumers ask the rule; none keeps an `if`:
- `ChartToolbar.set_market(market)` (one `TimeframeSelection` feeds the pills and the picker, so both follow); it falls back and reports through `sig_timeframe_changed`. the required `LiveChartPorts.market` makes every `LiveCandleChart` tell its toolbar and open on the nearest loadable timeframe (Market mode, Desk).
- `options_for_market(market)` in the picker catalogue backs `BackTestViewModel.timeframeOptions`; `RunSetupPanel` refreshes on `marketChanged`; `MarketSelectionCoordinator` falls back the selected timeframe and logs; `BackTestView` tells every chart host's toolbar (`IBacktestChartHost.set_market`), including hosts built later.
- `sync_intervals.py` derives the Data mode's list from `SYNC_MARKET`, the same value `SyncCoordinator` syncs.

Not changed in behaviour: the Bots charts (Spot bots) pass `MarketType.SPOT` and keep every timeframe; the CLI sync and stream commands are Spot-pinned and validate against `TimeFrame` as before.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/vo/market_timeframes.py` | the rule |
| `src/support/charting/chart_card/chart_toolbar.py`, `live_chart/live_chart_ports.py`, `live_chart/live_candle_chart.py` | toolbar `set_market` with fallback; the ports carry the market |
| `src/support/charting/timeframe_picker/catalogue.py`, `__init__.py` | `options_for_market` |
| `src/modules/trading/ui/market/market_chart.py`, `market_presenter.py`, `desk/desk_screen/desk_chart.py` | pass the chart's market |
| `src/modules/backtesting/ui/` (`backtest_view_model.py`, `run_setup_panel.py`, `coordinators/market_selection_coordinator.py`, `coordinators/factory.py`, `backtest_view.py`, `logic/backtest_chart_host.py`, `ports/i_backtest_chart_host.py`) | options follow the market; fallback and log; hosts follow |
| `src/modules/market_data/ui/sync_intervals.py`, `data_management_view_model.py`, `coordinators/sync_coordinator.py` | the Data mode's list from the rule |
| `tests/unit/architecture/baseline_god_files.json` | `backtest_view_model.py` 753 → 751 (the view model shrank); `backtest_view.py` stays at 400 |

## 5. Testing
Unit tier (`ci-rule.md` §2), each written before its code:
- `tests/unit/core/vo/test_market_timeframes.py` — the rule, the fallback, every market declares an entry.
- `tests/unit/support/charting/test_chart_toolbar_market.py` — a real `ChartToolbar`: `1s` gone on Futures from the pills and the grid, back on Spot; a Futures picker cannot choose it; fallback emits and logs.
- `tests/unit/modules/trading/ui/market/test_market_chart_timeframes_follow_market.py` — the real Market presenter: Spot → Futures → Spot; a `1s` default opens on `1m` on Futures and logs.
- `tests/unit/modules/backtesting/ui/test_backtest_timeframes_follow_market.py` — view model options, the run setup field, the coordinator's fallback and log, chart hosts (including one built after the switch).
- `tests/unit/modules/market_data/ui/test_sync_intervals.py` — the Data mode's list is the rule's list for the market `SyncCoordinator` syncs.

## Implementation notes (written when done)
- **Mutation check:** ten mutations, each run against its tests, each killed: Futures allowing `1s` in the rule; the toolbar offering everything; the toolbar not choosing the fallback; the Backtest options ignoring the market; the run setup not refreshing on `marketChanged`; the coordinator not falling back; the view not telling its hosts; the live chart not resolving its opening timeframe; the Market chart not passing its market; `SYNC_MARKET` moved to Futures.
- **Behaviour change recorded in an existing test:** the Backtest's default market is Futures, so its timeframe field now offers fifteen timeframes by default (`test_run_setup_choices.py`, which now asserts sixteen on Spot and fifteen on Futures).
- **Review round 1:** the Backtest's remembered state restored `timeframe` before `market`, so a remembered Spot `1s` was rejected under the Futures default and lost; `market` is now restored first (`test_a_remembered_spot_one_second_survives_a_futures_default`, red before for that reason). `LiveChartPorts.market` is now required, the Bots charts passing `MarketType.SPOT` explicitly, so a caller cannot forget it.
- **Not done, on purpose:** `BUG-166` (a)–(c) (the tick mode's tooltip and failure text, the locked real-time row, "On order fill" in bar-close mode) stay open; `BOT-168` is the real remedy for (a).
- **Verification:** `scripts/ci-local.ps1 -SkipTests` PASS (ruff, format, mypy, reference check; log `logs/ci-local-20261007-043709.log`, grepped for `FAILED|ERROR|Traceback|ResourceWarning`: no hit); `tests/unit/architecture` 618 passed; the whole unit tier passed (8458 tests). The full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR head.
