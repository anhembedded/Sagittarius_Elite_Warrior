# EPIC-038A — The app boots with PySide6 absent, and CI keeps it so

**Status:** ✅ Done (2026-10-12)
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
- [x] Before any headless code is written, the mechanisms headless work reuses are in the capability catalog (`.claude/rules/capabilities.md`, `EPIC-037A`): a `Capability:` block for the command dispatcher (`ICommandDispatcher`), the module CLI contribution hook (`declare_cli` and its registry), the data-root instance lock (`acquire_instance_access`) and the app configuration loader (`load_app_config`), and the catalog regenerated with `python3 scripts/render_capability_index.py --write`. The owner's reason (2026-10-12): the later EPIC-038 tasks must reuse these instead of building a second set. Done in commit `062e7f8`; `src/shell` joined the generator's scan roots because two of the four live there.
- [x] `create_app(...)`, `app.boot()` and `app.stop()` complete in a process where `PySide6`, `PySide6.*`, `shiboken6` and `pyqtgraph` cannot be imported **and** `importlib.util.find_spec` reports them absent (the VPS without Qt), with an empty data root and no credentials. The shared composition's engine extensions boot (nine: the 11 the DESIGN counted included the two GUI-only checks that moved, see Implementation notes), `BotsModule.boot` logs its four "Bots …" lines, `stop` closes the workers.
- [x] The GUI entry point's behaviour is unchanged: it still registers the UI-failure subscriber, the asset validator and the Qt package check, in the same order relative to `boot()`. A test builds the GUI composition and asserts all three are present.
- [x] The shared path (`create_app`) names no UI package: a source scan fails if `composition_root.py` or anything it imports at module level imports `PySide6`, `pyqtgraph` or `sagittarius_engine.extensions.pyside_mvc` (type-checking-only imports excepted, as today's three).
- [x] The guard runs in CI (`tests/sanity/`, sequential) as a **subprocess** with `sys.modules["PySide6"] = None` (and the others), and a second case with PySide6 importable but no `QApplication`; and it is shown **red** on the unmodified `master-warrior` before the fix.
- [x] A headless requirements file lists the runtime dependencies without PySide6, `pyqtgraph`, `pytest-qt`; `requirements.txt` is unchanged for the GUI (O6; approval first).
- [x] No Engine file is edited (O7). If a Qt import survives only because of an Engine module, the task stops and reports it rather than editing the Engine.

## 3. Design
Split the composition into **common** and **GUI additions** — the shape `app_bootstrapper.py` already uses for the GUI toast channel ("added later, once a `MainWindow` exists"). `create_app(config, instance, *, presentation)` or, cleaner, two functions: `create_app` (everything both entry points need) and `add_gui_wiring(app)` (UI-failure subscriber, asset validator, Qt package check) called by the GUI bootstrapper. Interface segregation: the headless entry point receives a composition that has never heard of Qt. The UI-failure subscriber is moved, not rewritten: `EPIC-036B` replaces `NotificationEventHandler` later and must find the same seam. A subscriber that only the GUI can feed (a UI action failed) has no business in a process with no UI.
Alternatives considered: wrapping the Engine import in `try/except ImportError` (hides the next Qt import behind a silent skip — the forgiving double of `EPIC-037`); moving `UiActionFailedEvent` into a Qt-free Engine module (an Engine change, O7).

## 3a. Reuse
Checked `.claude/rules/capabilities.md` and `src/support/` for what this task is about to build: it builds no widget, flow or helper a row covers. It does not build a second boot path — it splits the one `create_app` already is. Instance lock (`acquire_instance_access`), configuration (`load_app_config`), CLI table (`declare_cli`) and the dispatcher (`ICommandDispatcher`) are used as they are by `main.py`; this task adds their catalog rows, nothing else around them. The GUI toast channel's two-phase pattern in `app_bootstrapper.py` (`add_channel` once a window exists) is the model for the GUI additions: `used` the pattern, `not used` any new registry.

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
Written 2026-10-12 on branch `claude/epic-038a-qt-free-boot`, from `master-warrior` `d0410c4` (the task text cites `9a6099c`; the master moved, the defect did not). The engine is the pinned `f4ef582`; no Engine file was touched (O7).

**What was split.** `create_app` (`shell/composition_root.py`) now builds only what every entry point needs. `create_gui_app` (`shell/gui_wiring.py`) is `create_app` plus `add_gui_wiring`, and the GUI bootstrapper calls it in place of `create_app` (one call, so the additions cannot be forgotten and are always on before `boot()`). Four things moved behind it:
1. the **UI-failure subscriber** (`shell/ui_action_failure.py`: `from_ui_action_failed` and `UiActionFailureSubscriber`). `SystemFailureLog` and `NotificationEventHandler` keep only `TaskFailed` (and the bulk-sync event); the subscriber calls `SystemFailureLog.report` then `NotificationEventHandler.notify` in the order the two used to hear the event. Moved, not rewritten: `NotificationEventHandler` gained nothing but a public `notify` (the former `_notify`), so `EPIC-036B` replaces one constructor argument in the subscriber and deletes the handler.
2. the **asset validator** (`AssetValidatorExtension`);
3. the **Qt package check** (`shell/qt_package_check.py`: the Engine's `DependencyValidatorExtension` wrapped for `PySide6`, `pyqtgraph`; the shared one keeps `sqlalchemy`). Wrapped, not subclassed or instantiated twice: the Engine keys an extension by class name, and a subclass would be counted as a second presence check by the `BOT-119` test;
4. the **Engine-build check** (`EngineCapabilityValidatorExtension`) — **a fourth blocker the DESIGN did not list.** Both capabilities it declares are the Engine's Qt workbench classes, so at `boot()` it imported `pyside_mvc` (and, with PySide6 absent, reported the engine as *stale* — the misleading diagnosis it exists to prevent). It fires after the import-time blocker it hid behind, which is why the probe of 2026-10-09 never reached it. Fixed in the app: no Engine edit.

**Boot order kept.** The three checks used to boot before every module because `create_app` registered them first. The GUI wiring registers after the modules, so `AssetValidatorExtension`, `EngineCapabilityValidatorExtension` and the Qt check carry `priority = PREFLIGHT_BOOT_PRIORITY` (`core/contracts/boot_priority.py`); the Engine boots a higher priority first. `test_the_gui_checks_boot_before_any_module` boots the GUI graph and reads the Engine's `sorted_extensions`; removing the priority from the asset validator turns it red (mutation-checked).

**Layer placement.** The first placement under `presentation/ui/` was refused by `test_module_boundaries.py` (presentation may not import the shell or infrastructure; only `app_bootstrapper` may). The additions are composition, so they sit in `shell/`; `shell/gui_wiring.py` is added to `COMPOSITION_ROOT_FILES` beside `composition_root.py` because it names an infrastructure adapter. No allowlist or baseline line was added. The bootstrapper (`470` lines, over the ceiling, may not grow) changed one import and one call: 470 → 470.

**The guard, red first.** `tests/sanity/test_the_app_boots_without_pyside6.py` runs three subprocess cases. Before any change to the composition root, on the tree at `d0410c4`, `test_create_app_boots_and_stops_with_pyside6_blocked` failed with `ModuleNotFoundError: No module named 'PySide6.QtCore'` at `src/shell/system_error_report.py:41` ← `sagittarius_engine/extensions/pyside_mvc/safety/thread_affinity.py:6` (the reason the task names), and the PySide6-importable case failed on its `sys.modules` assertion (the shared path imported `PySide6`). `test_find_spec_reports_the_blocked_packages_absent` passed on both trees (the harness is honest). After the change all three pass. Re-planting the original defect (the Engine import in `system_error_report.py`) turns both boot cases red again.
`tests/unit/architecture/test_the_shared_composition_path_imports_no_ui_package.py` is the static half (module-level imports reachable from `composition_root.py` and `main.py`); planting `import PySide6` in `composition_root.py`, or the Engine import in `system_error_report.py`, fails it naming `file:line`.

**Verified outside the harness.** A clean virtual environment holding only the proposed headless set (`python-binance requests sqlalchemy pydantic pyarrow keyring`, versions from `requirements.lock` as constraints, plus the pinned Engine; 42 packages, `find_spec` of `PySide6`, `pyqtgraph`, `shiboken6` all `None`): `create_app`, `boot()`, `stop()` complete (nine extensions, the four "Bots …" lines, "App stopped."), and `python -m Sagittarius_Elite_Warrior.src.main exchange-status` runs. No exchange was contacted; the data root was empty and no credentials were set.

**Tests changed (P8, nothing weakened).** The UI-slot cases of `test_system_failure_log.py`, `test_notification_event_handler.py` and `test_system_error_report.py` moved to `tests/unit/shell/test_ui_action_failure.py` with the same assertions, against the same two sinks, plus a debounce case through `notify()`; the graph tests now say which graph hears which event (`test_gui_wiring.py`: the GUI graph hears all three, the shared graph registers none of the GUI additions and no `UiActionFailedEvent` handler). The three recording doubles those files each carried are one module, `tests/unit/shell/failure_doubles.py`. The sanity `booted_app` fixture builds the GUI graph (`create_gui_app`), because that tier proves the application the GUI runs.

**Verification (head of this branch, before the PR).** Commit tier `ci-local.ps1 -SkipTests`: `RESULT: PASS`, log scanned for `FAILED|ERROR|Traceback|ResourceWarning`: none. `tests/unit/architecture` + `tests/unit/shell` + `tests/unit/presentation` + `tests/unit/support/ui_kit` + `tests/unit/infrastructure`: 1592 passed; `tests/sanity`: 45 passed. The `-Full` run is GitHub Actions' on the PR head; not run locally.

**Owner decision O6, 2026-10-12: approved** ("ok thêm"), relayed by the coordinator session. `requirements-headless.txt` lists `python-binance requests sqlalchemy pydantic pyarrow keyring`, no version of its own: the install is `uv pip install -r requirements-headless.txt -c requirements.lock` then `scripts/engine_pin.py install`, so `requirements.lock` stays the one source of versions (no second lock, `requirements.txt` unchanged). `test_headless_requirements_name_no_qt_package` (in `test_dependency_pins.py`) asserts no Qt package, every name pinned in the lock and present in `requirements.txt`; adding `PySide6` to the file turns it red. Verified in a clean venv with that set (42 packages, no Qt): boot, stop and `exchange-status` run.

**Pre-existing, not this task's.** `tests/integration/presentation/ui/test_workbench_conformance.py::[True-1024x700]` (backtest `fits_the_window`) fails locally on the untouched base `d0410c4` too (container font metrics).

**Not covered by this task.** A bot with live orders run headless (the epic runs nothing against an exchange); `stop()` on SIGTERM (038D).
