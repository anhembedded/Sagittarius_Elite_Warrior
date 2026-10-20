# EPIC-043B — Option A: the colour scheme is chosen in Tools → Options, and the series colours are contrast-checked in both schemes

**Status:** ✅ Done (2026-10-20; pull request open)
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** [EPIC-043A](EPIC-043A_verify_dark_scheme.md)

---

## 1. Context and problem
Tools → Options gets System (default), Light, Dark, applied with `QStyleHints.setColorScheme`; no palette, style sheet or colour is written. The series colours (`series_colours.py`) are checked for contrast in both schemes, with one alternative per scheme where one fails (PRO-009 §2 A). Amends `ui-presentation-rule.md` where it says visual design is deferred.

## 2. Acceptance criteria
- [x] Options offers System, Light and Dark; System is the default; the choice persists and applies without a restart. (Tools → Options → Appearance; `ColourSchemePreference` remembered through `ui_state`; applied at start and on Apply. The restart-free half is proved by `EPIC-043A`'s runtime switch; the real platform effect is Not verified here, see Implementation notes.)
- [x] No `setStyleSheet`, `QPalette` write or colour literal is added in `src/`; the three guards are unchanged. (`test_stock_controls_only.py`, `test_no_global_stylesheet.py`, `test_app_styling_only_shrinks.py` untouched and green; the only palette in the change is the test harness's stand-in.)
- [x] A test fails when a series colour falls under the contrast threshold in either scheme. (`test_series_colours_contrast.py`: 21 series × white, `#1e1e1e` and `#202020`; mutation red.)
- [x] Preview frames in both schemes at 1024×700, 1366×768 and 1920×1080, and the conformance suite passes at all three sizes in both. (`test_workbench_screenshots.py` 36 frames; `test_workbench_conformance.py` unchanged and green, Options is not a mode.)

## 3. Design
**The choice.** `ColourSchemePreference` (`support/ui_kit/services/`) holds `ColourSchemeChoice` (System, Light, Dark) and is remembered through `ui_state`, exactly as `DisplayTimezonePreference` is (`BOT-205`): no new config key, so no config or dependency change. `ColourSchemeApplier` (`support/ui_kit/`) subscribes to it and calls `QStyleHints.setColorScheme(Light|Dark)`, or `unsetColorScheme()` for System; the application writes no palette. It is built and applied in `register_remembered_state` (after `QApplication`, before the first window), not in the bootstrapper, which may only shrink. `AppearanceOptionsPage` (`shell/appearance_options/`) is an `IOptionsSection` modelled on `DeveloperOptionsPage`: radio buttons, written only on OK or Apply. It sits after the modules' pages and before Developer, so Options still opens on Trading.

**The series colours.** The 043A measure showed 9 of 21 colours under 3:1 on white and 1 on dark. PRO-009 said one alternative per scheme; **that is not what is built, and the reason is recorded here for the owner to veto.** `series_colour()` is read once, when a series is built, by ~24 call sites (`BULL_COLOR` and `BEAR_COLOR` are import-time constants), so a second table keyed by scheme would never reach a line already drawn and would need a repaint seam across the charts. Instead the nine colours moved to the nearest tone of the same hue that reads on white and on both usual dark bases, so one value serves both schemes, with no state and no seam (`CONSTITUTION` P5/P6: the simpler mechanism that meets the criterion). The visible change is small: for example candle green `#26a69a` → `#25a296` (it was 2.998:1), orange `#e67e22` → `#df7619`, yellow `#f1c40f` → `#ae8e0a`, which is darker on a dark chart than before. Reverting a line of `series_colours.py` reverts it; the contrast test then names the series.

**What is not claimed.** `setColorScheme` has no effect on Qt's offscreen, minimal and xcb platforms (`EPIC-043A`). The tests prove the call is made with the right scheme, at start and on a change, and is remembered; only a Windows or macOS host shows the platform drawing it, so the look is the owner's to judge there.

## 3a. Reuse
`DisplayTimezonePreference` shape (preference + `IStateContributor` + `register_remembered_state`): used as the model, not extended (a different value, no shared base). `DeveloperOptionsPage` / `IOptionsSection` / `OptionsDialog`: used. `plain_label`, not needed. `series_colours.py`: changed in place. `capabilities.md`: two rows added (`render_capability_index.py --write`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/ui_kit/services/colour_scheme_preference.py` | new: the choice, remembered |
| `src/support/ui_kit/colour_scheme_applier.py` | new: asks Qt for the scheme |
| `src/shell/appearance_options/appearance_options_page.py` | new: Tools → Options → Appearance |
| `src/shell/options_pages.py` | Appearance before Developer |
| `src/presentation/ui/remembered_state_wiring.py` | registers the preference, builds and applies the applier |
| `src/support/charting/contracts/series_colours.py` | nine colours moved to read on both schemes |
| `.claude/rules/ui-presentation-rule.md`, `.claude/rules/capabilities.md` | the rule states the choice; two catalog rows |
| `tests/…` | preference, applier, page, start-up wiring, contrast guard; harness frames of the Options page |

## 5. Testing
- New: `test_colour_scheme_preference.py`, `test_colour_scheme_applier.py`, `test_appearance_options_page.py`, `test_colour_scheme_is_applied_at_start.py`, `test_series_colours_contrast.py` (all green). Updated to follow the table: `test_series_colours.py`, `test_script_series_colours.py`, `test_options_pages.py`.
- Mutation (testing-rule): removing `apply_now()`, the `set_on_changed` line, the `ColourSchemePreference` container registration, the `restore_into` line, or the Options page each turns a test red; restoring an old failing yellow turns the contrast guard red. Review round 1 found that the applier needed no container registration of its own (its subscription to the preference keeps it alive), so that line was removed rather than tested.
- Not verified: the dark chart `Base` on a real Windows or macOS dark session. The contrast guard stands on white, `#1e1e1e` and `#202020`; the margins are thin (most moved colours 3.10–3.16:1), and the RSI purple `#984bb8` would fall to 2.72:1 on `#2b2b2b`. When the owner checks a dark host, the measured `QPalette.Base` is to be recorded here; a base lighter than `#202020` means that colour needs another tone.
- Frames: `dialog~options-appearance[~dark].png` and the 36 mode frames, in the pull request.
- Not run: a real Windows or macOS dark session, Windows High Contrast.

## 6. Docs touched
`.claude/rules/ui-presentation-rule.md` (§ intro and §1: the scheme is a choice, series contrast), `.claude/rules/capabilities.md` (generated). HLD §11.4 and `EPIC-033` D8 were amended by the documentation pull request. `src/shell/` has no `Docs/MODULES/` folder.

## Implementation notes
**Delivery:** pull request on `claude/epic-043b-options-colour-scheme`, stacked on #647 (043A) and #646 (the epic); reviewed by a separate session; the owner merges.
