# EPIC-033M — The kit, the palette and the theme bootstrap are deleted; every ratchet becomes a ban

**Status:** ✅ Done (2026-10-06)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟢 — a shared surface changes shape
**Complexity:** M — deletion
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033H, EPIC-033I, EPIC-033J, EPIC-033K, EPIC-033L, EPIC-033N, EPIC-033P

---

## 1. Context and problem
HLD §11.4 makes deleting `Palette`, `kit/style.py` and `seed_app_theme()` the last step, once nothing reads them; `kit/` is 29 files (~4,578 lines) with 47 importers in `src`.

## 2. Acceptance criteria
- [x] `src/support/ui_kit/kit/`, `palette.py`, `theme_bootstrap.py`, `PageShell`, `StyledButton`, the sidebar and every replaced screen are deleted; `configure_app_qml` and `get_theme_bridge` are no longer called.
- [x] `baseline_stock_controls.json`, `baseline_workbench_conformance.json` and `baseline_app_styling.json` are empty and their guards become bans. **Partly, by the user's decision (2026-10-06):** every rule is a ban except `color_literal`, which still holds the data series colours (indicator lines, strategy markers, the chart's bull and bear) and moved to `BOT-161`.
- [x] `StrategyParamsDialog` (`src/support/ui_kit/param_form/`) is rebuilt from stock controls, its commit buttons a `QDialogButtonBox` (`ui-presentation-rule.md` §7), for both callers: the bot's strategy parameters and the Market mode's Tools → Indicator parameters… (`BOT-153`; the review of PR #369).
- [x] No `PySide6.QtCore.Property` is left in `src/` (`BUG-152`: a `QObject` class with a `Property` alive at exit leaves an uncollectable object at shutdown in PySide6 6.9–6.11). A view model's `Property` becomes a plain Python property or attribute, with a `Signal` where a reader needs change notification. Readers through Qt's meta-object system found by grep on 2026-10-06, each to be migrated first: `src/support/ui_kit/kit/binding.py:100-139` (`metaObject().indexOfProperty`, `property`, `setProperty`, `notifySignal`) and `kit/widget_value.py` (`userProperty` on widgets, not view models); by-name `.property(...)` reads in `src/modules/backtesting/ui/run_setup_panel.py`, `result_panels.py`, `run_progress_status.py`, `src/modules/bots/ui/bots_screen/bots_view.py:262`; and `.property`/`.setProperty` in `src/modules/market_data/ui/data_command_binding.py:66-102`. No QML or `QQmlPropertyMap` reader remains in `src/`. `backtest_state_fields.py:121` reads `<attr>Changed` signals by name, which the migration must keep.
- [ ] The app no longer imports the Engine's `kit` `CardModel` or theme bridge at runtime. **Moved to `BUG-152`** (the user's decision, 2026-10-06): the app calls neither, but `sagittarius_engine.extensions.pyside_mvc` imports its QML layer at package import, so any use of the package loads `CardModel`; and three app view models still subclass `BaseQmlViewModel`.
- [ ] A sanity run's log has no `uncollectable objects at shutdown` line (`BUG-152`), and then the gate's run-log scan fails on that `ResourceWarning`, so `ci-rule.md` §1's prescribed grep regains its meaning. **Moved to `BUG-152` with the criterion above:** 5 uncollectable objects remain, all from the Engine's `CardModel` and `BaseQmlViewModel`.
- [x] HLD §11.4's last row is marked done with the commit.

## 3. Design
Strangler Fig's last step (HLD §6.3).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/ui_kit/` | Deleted parts |
| `tests/unit/architecture/test_app_styling_only_shrinks.py` | Becomes a ban |

## 5. Testing
Full gate; conformance suite with an empty baseline.

## Implementation notes (written when done)
Three parts on one branch (`claude/confident-dirac-le8m4x`), the first two in parallel sessions on side branches:
- **Part A, `src/modules`:** every screen off the kit, `Palette`, `StyledButton`, `PageShell` and `QtCore.Property`; by-name `.property()` readers became typed access; figures painted by tone read `src/support/ui_kit/meaning_colours.py`, the one meaning table.
- **Part B, `src/support`:** `StrategyParamsDialog` (`BOT-153`), the symbol, time-range and timeframe pickers and the environment banner are stock dialogs and widgets; `StatusMessageViewModel` has plain Python properties; `chart_card/theme.py` names meanings, not tokens.
- **Part C:** `kit/`, `palette.py`, `theme_bootstrap.py`, `embed/` and its probe deleted (about 10,300 lines with their tests); the bootstrapper seeds no theme and registers the banner on `WorkbenchSurface` only; `CriticalErrorDialog` rebuilt as a stock dialog; the styling census held at zero (`baseline_app_styling.json` deleted), every stock-controls rule but `color_literal` a ban, the `QQuickWidget` guard a ban with no exemption, the Card guard deleted with the Card base it guarded. Part A's meaning table had written its colours as integers so the colour-literal guard would not see them; it now reads them from the chart theme's bull and bear, so no literal hides.
- **Not done here, by the user's decision:** the `color_literal` ratchet (`BOT-161`) and the last two criteria (`BUG-152`'s next step: the Engine loads its QML layer lazily, the app's three view models leave `BaseQmlViewModel`, then the gate fails on the warning).
- **Verification:** commit tier PASS; `tests/unit/architecture` 610 passed; unit + integration 8560 passed before the last test deletions (the failures were the deleted QML probes and the board rows fixed in #382); sanity 36 passed with the one known `uncollectable` line. The PR's `ci-local.ps1 -Full` run is the gate.
