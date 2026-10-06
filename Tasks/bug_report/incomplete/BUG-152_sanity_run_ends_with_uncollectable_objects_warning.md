# BUG-152 — A green gate's log ends with "ResourceWarning: gc: 5 uncollectable objects at shutdown"

- **Reported:** 2026-10-06 (the CI timing measurement for the user, reading the green `ci-local.ps1 -Full` run of PR #372)
- **Severity:** 🟢 P3 — no test fails, but `ci-rule.md` §1's prescribed grep for `ResourceWarning` matches on every green run, so the grep can no longer tell a new leak from this one
- **Status:** Open
- **Context:** The sanity tier's process (`tests/sanity/`) → interpreter shutdown → objects the garbage collector cannot free; owning module Not yet established
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
**Not in this PR.** The leak is removed at its source by `EPIC-033M` (`Tasks/epics/EPIC-033_windows_workbench/incomplete/EPIC-033M_retire_kit.md`), not suppressed. Rejected: exempting the line from the gate's `ResourceWarning` grep (it hides the leak, `CONSTITUTION.md` P8) and bumping PySide6 (the leak is in 6.9 through 6.11).

Plan, recorded as `EPIC-033M` acceptance criteria:
1. The Engine's `CardModel` and theme bridge, the largest source, stop being imported by the app and are deleted with the kit.
2. Every `Property` in `src/` becomes a plain Python property or attribute, with a `Signal` where a reader needs change notification, after the meta-object readers are listed and migrated.
3. A sanity run's log has no `uncollectable objects at shutdown` line; the gate's run-log scan then fails on that `ResourceWarning`, so the prescribed grep regains its meaning.

## Regression test
Not written: the fix is the deletion of the leak's source (`EPIC-033M` criterion (c) is its check, a sanity log with no uncollectable line).

## Verification
Not run.

## Suggested next steps
- Run the sanity tier with `gc.set_debug(gc.DEBUG_UNCOLLECTABLE)` to list the five objects and their types.
- Decide which test or fixture leaves them: bisect the 38 sanity tests.
- Once it is fixed, the gate's log scan could fail on this line, so the prescribed grep regains its meaning.
