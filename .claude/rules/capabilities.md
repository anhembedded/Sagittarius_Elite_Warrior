---
description: The shared mechanisms this application already has (need, symbol, where, one current user), delivered whenever source code is opened so a change reuses one instead of building a second. The table is generated from `Capability:` docstring blocks.
paths:
  - "src/**/*.py"
---

# CAPABILITY CATALOG — find what exists before you write

*Capability* here means a shared mechanism a developer reuses (`Docs/VOCABULARY/README.md`); it is not the Engine-API sense in `engine_capabilities.py`. Class A of the bug reports ("did not reuse") is what this table answers: `BUG-155` (a free-text symbol field beside `SymbolPickerOverlay`), `BUG-165` (hand-built empty labels beside `empty_page`). `[eye]`

1. Before building a widget, a helper or a flow, find your need below by its words and its synonyms. A row fits: use its symbol. No row fits: search `src/support/` once more, then build. `[review: A7]`
2. Name what you checked in the task's **Reuse** section (`.claude/templates/task.md` §3a); a pull request without it fails review check A7. `[review: A7]`
3. Add a mechanism others will reuse by writing a `Capability:` block in its module docstring, or in the package's `__init__.py` docstring when the module is near the 400-line ceiling (shape: `scripts/render_capability_index.py`), then `python3 scripts/render_capability_index.py --write`. Never edit the table by hand: the guard compares it with the generator. `[guard: test_every_support_package_is_in_the_catalog.py]`

## Declared in code (generated)

<!-- capabilities:begin -->
| Need | Use | Where | Used by |
| :--- | :--- | :--- | :--- |
| Name a widget or factory by import path so boot imports no widget module (also: lazy import, deferred import, late import, contribution factory, PLC0415) | `Deferred` | `src/core/contracts/deferred.py` | `src/modules/trading/module.py` |
| Add a command-line command from a module, one class and one declaration (also: declare_cli, CLI command, subcommand, headless command, cli_commands.json, argparse verb) | `ICliRegistry`, `CliCommandDescriptor` | `src/core/contracts/i_cli_registry.py` | `src/modules/market_data/module.py` |
| Run an application command from anywhere that holds no handler (a screen, a CLI verb, a host) (also: dispatch, command bus, run a use case, start a bot from code, command handler lookup) | `ICommandDispatcher` | `src/core/contracts/i_command_dispatcher.py` | `src/modules/bots/ui/bots_screen/bot_actions_coordinator.py` |
| Tell the user about a failure or an event (also: error message, toast, message bar, notify, QMessageBox) | `INotifier`, `FailureNotice`, `FailureKind` | `src/core/contracts/i_notifier.py` | `src/modules/backtesting/ui/failure_reporting.py` |
| Add a pre-flight check from the module that knows the thing, one class and one declaration (also: preflight, pre-flight check, declare_operations, readiness check, startup check, IPreflightCheck) | `IOperationsRegistry`, `PreflightCheckDescriptor`, `IPreflightCheck` | `src/core/contracts/i_operations_registry.py` | `src/modules/trading/module.py` |
| Find the repository root, or where runtime data is written (also: data directory, state folder, logs path, parents[2], cwd) | `data_root`, `data_root_override` | `src/core/repo_root.py` | `src/modules/bots/composition/state_bindings.py` |
| Load the application's configuration the way every entry point does (files, --dev, --debug) (also: config loader, ConfigManager, app_config.json, user_config.json, argv flags, developer mode) | `load_app_config` | `src/shell/app_config.py` | `src/main.py` |
| Keep a short read-only command's log off its console, in a bounded file under the data root (also: --verbose, quiet console, bot list prints 60 log lines, cli log file, log rotation, one log file per process, stderr warnings only) | `prepare_cli_log`, `CliLogRouting` | `src/shell/cli_log_routing.py` | `src/main.py` |
| Take the data root's single-instance lock before building the app (one writable copy per data root) (also: instance lock, single instance, second copy, read-only copy, instance.lock, data root access) | `acquire_instance_access` | `src/shell/composition_root.py` | `src/main.py` |
| Send the console log to stderr for a run whose stdout carries a report (also: log to stderr, stdout is the report, --json log line, machine format, StdLogger writes to stdout, log.console.enabled) | `console_log_to` | `src/shell/console_log_stream.py` | `src/main.py` |
| Get a venue's API key and secret without reading env vars or files yourself (also: credentials, api key, secret, keyring, environment variable) | `IExchangeCredentialsProvider`, `ResolvedCredentials` | `src/support/binance_gateway/contracts/i_exchange_credentials_provider.py` | `src/modules/trading/adapters/binance/futures_account_control.py` |
| Name a trading venue (Spot or Futures, mainnet or testnet), never a raw string (also: venue, market type, testnet flag, endpoint) | `TradingVenue` | `src/support/binance_gateway/contracts/trading_venue.py` | `src/modules/bots/adapters/venue_fresh_price_reader.py` |
| Draw candles, indicator lines, markers and price levels on a chart (also: candlestick chart, OHLC, plot, pyqtgraph) | `ChartCard` | `src/support/charting/chart_card/` | `src/modules/backtesting/ui/logic/backtest_chart_host.py` |
| Put a chart's toolbar actions in a mode's menu as commands (also: menu, QAction, zoom command, chart toolbar) | `chart_commands` | `src/support/charting/chart_commands.py` | `src/modules/backtesting/ui/backtest_commands.py` |
| Show a chart that loads a symbol's history and stays live (also: live chart, streaming candles, ticker chart, kline stream) | `LiveCandleChart` | `src/support/charting/live_chart/` | `src/modules/bots/ui/chart/bot_chart.py` |
| Offer the timeframes a market supports, ordered and named (also: interval, candle size, 1m 5m 1h, kline interval) | `all_options`, `options_for_market`, `describe` | `src/support/charting/timeframe_picker/catalogue.py` | `src/modules/backtesting/ui/backtest_view_model.py` |
| Decide before the app boots whether a command needs the writable copy of the data root (also: read-only command, status, bot list, take the lock, writable instance, command changes nothing, read_only in cli_commands.json) | `command_is_read_only`, `command_requires_writable_instance`, `command_owns_its_lifecycle`, `command_keeps_log_off_console`, `command_needed_modules` | `src/support/cli_host/command_access.py` | `src/main.py` |
| Turn a command's result into the process exit status, one table for every command (also: exit code, sys.exit, CliOutcome, return code, failed command exits zero, non-zero exit, script can tell failure) | `exit_status_of`, `run_command` | `src/support/cli_host/exit_status.py` | `src/main.py` |
| Start the application in a mode from one command-line word (also: gui, shell, launcher verb, bare main.py, entry point, run mode, subcommand that opens a window) | `LauncherVerb`, `add_launcher_verbs` | `src/support/cli_host/launcher_verb.py` | `src/main.py` |
| Print a report command's result as text, JSON or any registered format (also: --json, --format, output format, machine-readable output, renderer, report command, key=value, CSV) | `emit_report`, `select_format`, `wants_machine_output` | `src/support/cli_host/report_output.py` | `src/presentation/cli/exchange_status_cmd.py` |
| Look up or register a chart indicator script by id (also: indicator, overlay, EMA line, script registry) | `IndicatorScriptRegistry` | `src/support/indicators/indicator_script_registry.py` | `src/modules/trading/ui/market/market_chart.py` |
| Add a chart indicator script (EMA 20/50/100/200, cross, ribbon, MACD, RSI 14 exist; copy one) (also: custom indicator, BaseIndicatorScript, overlay script) | `EmaCrossScript` | `src/support/indicators/indicator_scripts/ema_cross_script.py` | `src/shell/indicator_scripts.py` |
| Compute an indicator on candles (EMA, RSI, MACD, bands, ATR) (also: moving average, rsi, bollinger, atr, technical indicator) | `IIndicator` | `src/support/indicators/indicators/i_indicator.py` | `src/modules/strategy/domain/strategies/base_strategy.py` |
| Compare series in a script: crossings, above, constants (also: crossover, cross above, cross below, series compare) | `Series`, `crossed_above`, `crossed_below` | `src/support/indicators/scripting/series.py` | `src/modules/strategy/domain/strategies/ema_crossover_strategy.py` |
| Run indicator scripts on a chart's candles and name their lines (also: indicator lines, script runner, overlay lines) | `IndicatorScriptRunner`, `qualified_line_name` | `src/support/indicators/ui/` | `src/modules/backtesting/ui/coordinators/indicator_coordinator.py` |
| Read a named secret from wherever this host provides it (systemd credential, secret file, keyring) (also: secret store, credentials, LoadCredential, CREDENTIALS_DIRECTORY, keyring, webhook URL, API key, headless secret) | `build_secret_stores` | `src/support/secrets/` | `src/modules/trading/composition/adapter_bindings.py` |
| A panel's page while it has nothing to show, framed like a filled view (also: empty state, EmptyStateStack, no data label, placeholder, instruction text) | `empty_page`, `frame_instruction_page` | `src/support/ui_kit/empty_page.py` | `src/modules/bots/ui/bots_screen/bot_plan_panel.py` |
| Give every member of an enum a user-facing label (also: enum to text, display name, label table) | `EnumLabels` | `src/support/ui_kit/enum_labels.py` | `src/modules/backtesting/ui/logic/chart_controls.py` |
| Show the which-funds-am-I-trading banner (also: banner, testnet warning, mainnet warning, environment strip) | `environment_banner_factory` | `src/support/ui_kit/environment_banner/environment_banner_factory.py` | `src/presentation/ui/app_bootstrapper.py` |
| Colour something by meaning (good, bad, warning), never a hex (also: colour, red green, tone, palette, stylesheet) | `Tone`, `tone_colour` | `src/support/ui_kit/meaning_colours.py` | `src/modules/backtesting/ui/backtest_stat_row.py` |
| Edit a strategy's parameters in the shared dialog (also: params dialog, strategy settings, parameter form) | `StrategyParamsDialog` | `src/support/ui_kit/param_form/strategy_params_dialog.py` | `src/modules/bots/ui/strategies/arm_strategy_dialog.py` |
| Make a QLabel whose text is text, never markup (also: label, QLabel, setText, rich text) | `plain_label` | `src/support/ui_kit/plain_label.py` | `src/modules/backtesting/ui/_drawdown_chart_widget.py` |
| Ask the window to show a mode (also: navigate, open screen, switch mode, go to) | `INavigationService` | `src/support/ui_kit/registry/ports/i_navigation_service.py` | `src/presentation/ui/main_window.py` |
| Register a screen (mode) with the workbench (also: route, mode, screen descriptor, navigation entry) | `IScreenRegistry` | `src/support/ui_kit/registry/ports/i_screen_registry.py` | `src/shell/screen_wiring.py` |
| Show a time in the user's display timezone (also: timezone, utc offset, local time, datetime format) | `get_display_timezone_label`, `get_supported_timezones`, `format_display_datetime`, `get_utc_offset_seconds` | `src/support/ui_kit/services/display_timezone_service.py` | `src/modules/backtesting/ui/view_models/time_range_view_model.py` |
| Show rows in a table the one way every table here is shown (also: QTableView, table panel, grid, sortable table, empty table text) | `SpecTable` | `src/support/ui_kit/spec_table.py` | `src/modules/backtesting/ui/backtest_trade_logs_panel.py` |
| Remember a screen's UI state across runs (also: persist, restore, splitter, last symbol, favourites, ui_state.json) | `UiStateCoordinator` | `src/support/ui_kit/state/ui_state_coordinator.py` | `src/modules/backtesting/ui/backtest_presenter.py` |
| Choose a trading pair, with favourites and recents (also: symbol picker, pair chooser, ticker selector, market combo, symbol field) | `SymbolPickerOverlay`, `ISymbolPickerSource` | `src/support/ui_kit/symbol_picker/` | `src/modules/bots/ui/bots_screen/new_bot_dialog.py` |
| Model rows for a table view (also: QAbstractTableModel, row model, table data) | `RowTableModel` | `src/support/ui_kit/table_model.py` | `src/modules/backtesting/ui/metric_comparison_model.py` |
| Pick a start and an end time (also: date range, from and to, period) | `TimeRangePickerDialog` | `src/support/ui_kit/time_range_picker/dialog.py` | `src/modules/backtesting/ui/backtest_modals/time_range_picker_dialog.py` |
| Hand a worker thread's answer to the UI thread (also: background thread, QThread, signal, async result, main thread) | `UiThreadRelay` | `src/support/ui_kit/ui_thread_relay.py` | `src/modules/bots/ui/bots_screen/fenced_reads.py` |
| Write a price, number, percentage or time for display (also: format, decimals, number to text, f-string, round) | `APP_VALUE_FORMATTER`, `write_value` | `src/support/ui_kit/value_formatter.py` | `src/modules/backtesting/ui/coordinators/data_sync_coordinator.py` |
| Ask a risky action's question, answered with its own verbs (also: confirm, are you sure, QMessageBox, yes no dialog) | `VerbQuestion`, `ask_with_verbs` | `src/support/ui_kit/verb_confirmation.py` | `src/modules/trading/ui/desk/order_entry/order_entry_panel.py` |
<!-- capabilities:end -->

## Not declared in code (hand-written)

| Need | Use | Where |
| :--- | :--- | :--- |
| A widget family the app wraps from the Engine (`EmptyStateStack`, `Selection`, `IValueFormatter`) | `sagittarius_engine.extensions.pyside_mvc.workbench` | the Engine repository, not this checkout |
