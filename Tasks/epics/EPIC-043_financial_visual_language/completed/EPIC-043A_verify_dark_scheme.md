# EPIC-043A — Verify: every mode under the dark scheme at 1366×768

**Status:** ✅ Done (2026-10-20; pull request open)
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟢 — read-only evidence
**Complexity:** S — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** None

---

## 1. Context and problem
Screenshot every mode under the dark colour scheme at 1366×768, offscreen with `QStyleHints.setColorScheme` or the platform, and record what already reads well and what does not (PRO-009 §4 step 1). Nobody has looked yet (PRO-009 §1, Unknown).

## 2. Acceptance criteria
- [x] A frame of every mode in the dark scheme at 1366×768 exists (and at 1024×700 and 1920×1080), with the exact command that produced it (§5).
- [x] The task records, per mode, what reads well and what fails (Implementation notes).
- [x] Whether `setColorScheme` is available and effective offscreen is recorded as a fact (Implementation notes; `requirements.lock` pins PySide6 6.11.1).

## 3. Design
The existing screenshot harness (`workbench_screenshots.py`, the real `MainWindow` over seeded fakes, drawn by `QWidget.grab()`) gains a colour scheme: `apply_scheme` asks Qt for Dark with `QStyleHints.setColorScheme`, the call Tools → Options will make, and where the platform theme ignores it, lays a standard dark `QPalette` from the test. The scheme is switched **at runtime, after the window is built**, which is how Options → Apply will switch it, so the frames also answer whether the app follows a switch without a restart. The app itself writes no palette. No new tool: the extension the harness's docstring already named ("a dark palette, once the app follows one").

## 3a. Reuse
Used `capture_modes`, `screenshot_name`, `is_blank` and the `main_window` / `navigate` fixtures (`capabilities.md`: no UI need of its own; this is test tooling).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/integration/presentation/ui/workbench_screenshots.py` | `SCHEMES`, `apply_scheme`, `restore_scheme`, `AppliedScheme`; `capture_modes` and `screenshot_name` take a scheme (`route~dark@WxH.png`; the light name is unchanged) |
| `tests/integration/presentation/ui/test_workbench_screenshots.py` | Each mode at each size in each scheme; fails when a frame named dark was drawn with a light window colour |

## 5. Testing
- `SEW_UI_SCREENSHOTS=<dir> PYTHONPATH=.. QT_QPA_PLATFORM=offscreen pytest tests/integration/presentation/ui/test_workbench_screenshots.py` — 7 passed, 36 frames (6 modes × 3 sizes × 2 schemes). Review round 1 (the reviewer session's comment on #647) added the bevel roles to the stand-in, removed an assertion that could not fail, and corrected this record.
- Mutation: replacing the palette stand-in with a no-op turns the dark case red (`window_lightness` stays light); restored, green.
- Not run: a real Windows dark session (the platform's own dark style), Windows High Contrast.

## 6. Docs touched
none, because this is test tooling and evidence; `ui-presentation-rule.md` and the HLD are amended by the documentation pull request and by 043B.

## Implementation notes
**Facts established (PySide6 6.11.1, measured 2026-10-20):**
- `QStyleHints.setColorScheme(Qt.ColorScheme.Dark)` exists and is accepted, but on Qt's `offscreen`, `minimal` and Linux `xcb` platforms (this container) `colorScheme()` stays `Unknown` and the application palette does not change: the platform theme there does not implement the request. It can only be proved on a Windows or macOS host, so **043B must not claim the real effect from this container**; it tests the code path (the call is made, the setting persists and is reapplied at start) and the owner's host judges the look.
- Under a dark palette laid at runtime, **every mode redraws dark without a restart**, and the chart chrome (plot background, axes, grid, crosshair label) follows `QPalette` as `chart_chrome.py` promises. So "System / Light / Dark applies on Apply" needs no widget rebuild.

**Per mode, dark, 1366×768 (frames in the pull request):**
| Mode | Reads well | Does not / notes |
| :--- | :--- | :--- |
| Market | Menus, toolbar, tabs, watchlist, Output pane, chart background, axes and candle bodies; mode-bar icons turn light | Seeded fixture shows only up candles in the bull teal; no loss colour is visible anywhere (PRO-009 §1: outside backtesting profit and loss are uncoloured). The empty Watchlist columns are the fixture, not a defect |
| Trade | Order entry (fields, tabs, sliders, disabled buttons), positions, account summary | Disabled controls (`New order`, `Buy/Long`) are low contrast by Qt's disabled group, the platform's choice. **Check boxes (*Reduce-only*, *TP/SL*)** were dark squares with almost no border under the first stand-in palette; with the five bevel roles set (`Light`, `Midlight`, `Mid`, `Dark`, `Shadow`) they show a border, so that part was the stand-in, not the app. **The toolbar's overflow chevron (`››`)**, which says more commands exist at 1024×700, is faint in light and fainter in dark: a Qt-drawn mark that is the platform's own, to be judged on the owner's host |
| Bots | Bots/Strategies tables, empty-state sentences, Live and Backtest tabs, Plan dock | `Not armed` and every state is plain text: B2 (state badges) has nothing yet to tone. `BOT-209` is reworking the Plan dock, so its look is not judged here |
| Data management | Table, Gaps, Output, empty-state sentences | none |
| Backtest | Run setup form, chart, metrics, trades, tabs | Chart axes show `00.100`-style ticks on an empty fixture: not a dark-scheme matter. The chart toolbar's `››` overflow chevron is faint, fainter in dark (as for Trade) |
| Developer | Event table, trading-session read-out | none |

**Caveat on every row above:** the frames are drawn under a **stand-in** dark `QPalette` laid by the test, not the platform's own dark style, because Qt's offscreen platform ignores `setColorScheme`. The stand-in sets the surface, text, button, highlight and bevel roles; Windows' own dark palette will differ, so bevels, stock icons and the faint overflow chevron are not judged here and are the owner's to check on a Windows host.

**What this changes for the epic:** PRO-009 §4 guessed that verification "may reduce A to the Options switch alone". The evidence supports that for the *palette* half: no screen fails to read in dark under the stand-in palette, with the overflow chevron the one mark that is faint in both schemes and worse in dark. A still has to add the Options choice and the series-colour contrast check (the frames cannot judge contrast numerically); the visible gain of the epic is B, where profit, loss and state are absent today.

**Delivery:** a pull request on `claude/epic-043a-verify-dark-scheme`, stacked on the documentation pull request (#646); reviewed by a separate session; the owner merges.
