# BUG-152 — A green gate's log ends with "ResourceWarning: gc: 5 uncollectable objects at shutdown"

- **Reported:** 2026-10-06 (the CI timing measurement for the user, reading the green `ci-local.ps1 -Full` run of PR #372)
- **Severity:** 🟢 P3 — no test fails, but `ci-rule.md` §1's prescribed grep for `ResourceWarning` matches on every green run, so the grep can no longer tell a new leak from this one
- **Status:** ✅ Fixed (2026-10-06)
- **Context:** The sanity tier's process (`tests/sanity/`) → interpreter shutdown → objects the garbage collector cannot free; owning classes: `QObject` classes with a `QtCore.Property`, last the Engine's `CardModel` and `BaseQmlViewModel`
- **Environment:** GitHub Actions `ubuntu-24.04`, Python 3.12.14, run 37409274117 (job 112093859516) on `3e78162`; the same line in a local sanity run in the cloud container on the same day.

## Reproduction
1. Run the gate, or the sanity tier alone: `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`, or `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/sanity -q`.
2. Grep the run's `LOG_FILE` for `ResourceWarning`.

**Expected:** no `ResourceWarning`; the run is green and its log is clean.
**Actual:** the line below, after the sanity tier's summary, on a run whose verdict is `RESULT: PASS`.

**Frequency:** every run seen (CI and local, 2026-10-06). When it began: Not yet established.

## Symptom
From the run's log file (`ci-local-logs` artifact, `logs/ci-local-latest.log`, lines 18884–18889):

```
============================= 38 passed in 44.65s ==============================
gc:0: ResourceWarning: gc: 5 uncollectable objects at shutdown; use gc.set_debug(gc.DEBUG_UNCOLLECTABLE) to list them
  ✅  Tests passed
  ✅  Sanity passed
```

## Root cause
**Established 2026-10-06; the source is PySide6, not a test or fixture.** Any class that subclasses `QObject` and defines a `PySide6.QtCore.Property` leaves one uncollectable object at interpreter shutdown, if the class is still alive at exit.

One-line repro and its controls (`QT_QPA_PLATFORM=offscreen python -W default -c ...`):

| Class body | Shutdown line |
| :--- | :--- |
| `class A(QObject): p = Property(int, lambda s: 1, constant=True)` | `gc: 1 uncollectable objects at shutdown` |
| the same with `notify=<Signal>`, with no notify, with a named getter, with the `@Property(...)` decorator | the same line, every shape |
| `class A(QObject): pass`, or only a `Signal` | nothing |
| a Property class, then `del A; gc.collect()` before exit | nothing (`gc.garbage` is empty) |

Versions tried: PySide6 6.11.1 (the pin in `requirements.txt`), 6.10.0 and 6.9.0 all print the line, so a version bump does not clear it.

`gc.set_debug(gc.DEBUG_UNCOLLECTABLE)` in the sanity tier lists `PySide6.QtCore.Property` objects, their getter `function`s and cells, a `Shiboken.ObjectType`, a `QMetaObject`, and a `SourceFileLoader`/`ModuleSpec` pair. `gc.garbage` is empty after `gc.collect()` at `pytest_unconfigure`, so these are not `__del__` cycles the tests left behind; Shiboken's type teardown refuses them.

Classes that define a `Property` and are alive at exit in the sanity run:
- Engine (`sagittarius_engine/extensions/pyside_mvc/`): `kit/card_model.py` `CardModel` (5 Properties, the count in the log line), `runtime/base_view_model.py` `BaseQmlViewModel`.
- App: `src/modules/backtesting/ui/view_models/{run_result,time_range,strategy_params,run_progress,broker_sim}_view_model.py`, `src/modules/backtesting/ui/backtest_view_model.py`, `src/modules/trading/ui/settings/trading_settings_view_model.py`, `src/modules/trading/ui/desk/desk_screen/desk_view_model.py`, `src/modules/market_data/ui/settings/market_data_settings_view_model.py`, `src/modules/market_data/ui/data_management_view_model.py`, `src/support/ui_kit/status_view_model.py`.

Importing only `sagittarius_engine.extensions.pyside_mvc.kit.card_model` in a bare interpreter already prints 7 uncollectable objects.

These Properties are QML-era leftovers: `src/` contains no `.qml` any more.

## Fix
Three steps, at the mechanism: no class the app loads declares a `QtCore.Property`.

1. **`EPIC-033M` (PR #383):** removed every `QtCore.Property` from `src/`.
2. **Engine `BUG-023` (Engine PR #235):** `pyside_mvc`, its `runtime` and its `kit` load the QML layer on first use, through a module `__getattr__`, not at package import. Importing any `pyside_mvc` module no longer brings `CardModel` and `BaseQmlViewModel` with it.
3. **This repository:**
   - **The view models:** `BackTestViewModel` and `DataManagementViewModel` now subclass `src/support/ui_kit/ui_mode_view_model.py` `UiModeViewModel`. It is the same `uiMode`, `controlsEnabled`, `set_ui_mode` and `DISABLED_UI_MODES` contract, as plain Python properties with the two change signals. `StatusMessageViewModel` is a plain `QObject`; it inherited the two Properties and used neither.
   - **The capability check:** the Engine capability check stops requiring `create_quick_widget(background=...)` (`src/infrastructure/engine_adapters/engine_capabilities.py`). The app builds no QML widget since `EPIC-033M`, and looking the symbol up loaded the Engine's QML layer, `CardModel` included, at every boot. That boot-time lookup was the last source of the 5 objects.
   - **The pin:** `engine.ref` moves to `31a523e`, which carries Engine #235.
   - **The gate:** the run-log scan (`scripts/ci-local.ps1` `Invoke-RunLogScan`) now also matches `uncollectable objects at shutdown`. The line prints at interpreter exit, after every test passed, so the gate is the only place that can fail on it.
   - **Thread-affinity sanity test:** `test_view_model_thread_affinity_sanity.py` discovers view models from the app's two bases instead of `BaseQmlViewModel`.

## Regression test
`tests/sanity/test_shutdown_leaves_nothing_uncollectable.py`, three tests:
- `test_no_src_module_loads_a_qobject_class_with_a_qt_property` runs a fresh interpreter, imports every module under `src/`, and fails on any loaded `QObject` class with a Property, or on the Engine's QML layer being loaded. It checks the mechanism; the warning's absence alone depends on module teardown order.
- `test_importing_the_view_models_exits_without_uncollectable_objects` runs a fresh interpreter that imports the three view models, and fails on the warning line.
- `test_the_booted_app_loads_no_qobject_class_with_a_qt_property` makes the same scan after the real boot (`booted_app`). Boot runs code an import does not, such as the capability check.

**Before**, with Engine `31a523e` installed:
- the `src` scan was red, listing the seven app view models on `BaseQmlViewModel`, the class itself and its module;
- the import test was red with `gc: 2 uncollectable objects at shutdown`;
- the boot scan was red with `kit.card_model.CardModel`, after the view models were already fixed.

**After:** all three are green.

## Verification
- Sanity tier: 40 passed. Grepping its output for `uncollectable` finds 0 lines, with and without `-W default`. Before the fix it printed `gc: 5 uncollectable objects at shutdown` on every run.
- Gate scan, probed by sourcing `Invoke-RunLogScan` in `pwsh`: a log holding the `gc:` line returns a hit labelled `uncollectable at shutdown : 1 (BUG-152)`, and a clean log returns none.
