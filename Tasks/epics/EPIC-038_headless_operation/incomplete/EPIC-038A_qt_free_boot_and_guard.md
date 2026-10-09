# EPIC-038A — The app boots with PySide6 absent, and CI keeps it so

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-09 (run bots with no GUI on a VPS); the coordinator's brief asked to prove first whether `create_app` boots headless. It does not: [DESIGN §1.1](../DESIGN_2026-10-09_headless_operation.md).
**Risk:** 🟡 — edits the composition root that every entry point passes through; a wrong move silently removes a GUI subscriber or validator
**Complexity:** M — three small relocations, one new guard, one requirements file
**Epic:** [EPIC-038](../README.md)
**SPEC:** [SPEC-011](../../../../Docs/SPEC/SPEC-011_start_the_app_and_choose_developer_mode.md) is read for the GUI boot journey this must not change; SPEC-015 (new, written by 038D) covers the headless one.
**Design:** [DESIGN §1, §3, §13](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§16](../RESEARCH_2026-10-09_headless_operation.md)
**Depends on:** owner decisions O6 (a headless requirements file is a dependency change) and O7 (no Engine change). Coordinates with [`EPIC-036B`](../../EPIC-036_alerting_module/incomplete/EPIC-036B_alert_sources.md), which deletes `notification_event_handler.py`.

---

## 1. Context and problem
Run on 2026-10-09 with the engine at its pin (`engine.ref` = `f4ef582`) and PySide6 absent or unimportable, `import composition_root` fails: `src/shell/system_error_report.py:41` imports `UiActionFailedEvent` from `sagittarius_engine.extensions.pyside_mvc.safety`, whose package `__init__` imports the Qt runtime. Two more UI concerns sit in the shared path: `AssetValidatorExtension` (`composition_root.py:284`, it reaches `support/ui_kit/assets/icon_loader.py`, which imports `QtGui`/`QtSvg`) and `DependencyValidatorExtension(["PySide6", "pyqtgraph", "sqlalchemy"])` (`composition_root.py:275`), which calls `sys.exit(1)` when PySide6 is not installed. With PySide6 installed and no window, the same boot succeeds and the bots start (DESIGN §1.1, run C). Nothing in CI would notice Qt creeping back: the unit suite runs with Qt installed.

## 2. Acceptance criteria
- [ ] `create_app(...)`, `app.boot()` and `app.stop()` complete in a process where `PySide6`, `PySide6.*`, `shiboken6` and `pyqtgraph` cannot be imported **and** `importlib.util.find_spec` reports them absent (the VPS without Qt), with an empty data root and no credentials. The 11 modules boot, `BotsModule.boot` logs its four "Bots …" lines, `stop` closes the workers.
- [ ] The GUI entry point's behaviour is unchanged: it still registers the UI-failure subscriber, the asset validator and the Qt package check, in the same order relative to `boot()`. A test builds the GUI composition and asserts all three are present.
- [ ] The shared path (`create_app`) names no UI package: a source scan fails if `composition_root.py` or anything it imports at module level imports `PySide6`, `pyqtgraph` or `sagittarius_engine.extensions.pyside_mvc` (type-checking-only imports excepted, as today's three).
- [ ] The guard runs in CI (`tests/sanity/`, sequential) as a **subprocess** with `sys.modules["PySide6"] = None` (and the others), and a second case with PySide6 importable but no `QApplication`; and it is shown **red** on the unmodified `master-warrior` before the fix.
- [ ] A headless requirements file lists the runtime dependencies without PySide6, `pyqtgraph`, `pytest-qt`; `requirements.txt` is unchanged for the GUI (O6; approval first).
- [ ] No Engine file is edited (O7). If a Qt import survives only because of an Engine module, the task stops and reports it rather than editing the Engine.

## 3. Design
Split the composition into **common** and **GUI additions** — the shape `app_bootstrapper.py` already uses for the GUI toast channel ("added later, once a `MainWindow` exists"). `create_app(config, instance, *, presentation)` or, cleaner, two functions: `create_app` (everything both entry points need) and `add_gui_wiring(app)` (UI-failure subscriber, asset validator, Qt package check) called by the GUI bootstrapper. Interface segregation: the headless entry point receives a composition that has never heard of Qt. The UI-failure subscriber is moved, not rewritten: `EPIC-036B` replaces `NotificationEventHandler` later and must find the same seam. A subscriber that only the GUI can feed (a UI action failed) has no business in a process with no UI.
Alternatives considered: wrapping the Engine import in `try/except ImportError` (hides the next Qt import behind a silent skip — the forgiving double of `EPIC-037`); moving `UiActionFailedEvent` into a Qt-free Engine module (an Engine change, O7).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/shell/composition_root.py` | remove `AssetValidatorExtension`, the Qt names in the dependency list and the UI-failure wiring from the shared path; keep `sqlalchemy` |
| the GUI bootstrapper (`app_bootstrapper.py`; locate when starting) | call the GUI additions |
| `src/shell/system_error_report.py`, `notification_event_handler.py`, `system_failure_log.py` | split what needs the Engine's Qt events from what does not; move the Qt-needing import behind the GUI additions (verify each file; do not rewrite what 036B deletes) |
| `tests/sanity/test_the_app_boots_without_pyside6.py` (new) | the guard |
| `tests/unit/architecture/` (a source-scan guard, new) | the shared path imports no UI package |
| `requirements-headless.txt` (new, after O6) | runtime set without Qt |

## 5. Testing
Tier: sanity (real composition root, sequential, `ci-rule.md` §2) plus an architecture guard.
- `test_create_app_boots_and_stops_with_pyside6_blocked` — subprocess, `sys.modules` blocks; asserts exit 0 and the bots' log lines. **Red first** on `9a6099c`.
- `test_find_spec_reports_the_blocked_packages_absent` — the harness itself is honest (it would pass vacuously if the block did nothing).
- `test_the_gui_composition_still_registers_the_ui_failure_subscriber_the_asset_validator_and_the_qt_check`
- `test_the_shared_composition_path_imports_no_ui_package` (source scan; mutation: add one `import PySide6` and see it fail)
- `test_headless_requirements_name_no_qt_package`
Manual: none. Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: write `test_create_app_boots_and_stops_with_pyside6_blocked` and run it red.
