# EPIC-043 — The desktop app reads like a financial application, through the platform's colour scheme and one meaning table

- **Status:** 🟡 Phase 1 in progress (2/5) — scaffolded 2026-10-20
- **Repositories:** Elite. No Engine change.
- **Origin:** the owner, 2026-10-13: *"add màu, theme cho app này thì có mất nhiều công sức ko bạn, UI bây giờ đơn điệu lắm thiếu nhiều design đặc trưng của 1 app tài chính"* (the UI is very plain and lacks the design of a financial app); accepted 2026-10-20 as [PRO-009](../../proposal/PRO-009.md), options A + B.
- **North star:** [PRO-009](../../proposal/PRO-009.md) §2 and [HLD §11.4](../../../Docs/HLD/11_desktop_workbench.md), as amended 2026-10-20.
- **Decisions:** [EPIC-033 D1 and D8](../EPIC-033_windows_workbench/DECISION_2026-10-04_windows_workbench.md) (D8 amended 2026-10-20; D1 unchanged).
- **Dependencies:** `BOT-209` (the Bots Plan dock rework, another session) must merge before `043C`. Runs in parallel with `EPIC-039`'s Testnet run.

---

## 1. Decisions already made
1. **A + B accepted; option C (a designed theme) rejected** (owner, 2026-10-20, PRO-009 §6).
2. **The default colour scheme is System**; Dark is chosen in Tools → Options (owner).
3. **The price tick flash is an Options toggle, off by default** (owner).
4. **D1 stays:** stock controls only. The scheme is applied through `QStyleHints.setColorScheme` (PySide6 6.11.1, `requirements.lock`); the app writes no palette, style sheet or colour for it, and adds no third-party theme package.
5. **Colour that carries meaning lives in `meaning_colours.py`** and always has a word, sign or icon beside it.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-13, `c5fe7c7`) | When the epic is done |
| :--- | :-: | :-: |
| Screens that tone profit and loss by `Tone` | `backtesting/ui` only (4 files) | Bots, trading and market screens too |
| Colour scheme chosen in the app | not possible; follows the OS | System, Light or Dark in Tools → Options |
| Modes verified under the dark scheme | 0 (nobody has looked) | every mode, at 3 sizes, in both schemes |
| Stylesheets, app palettes, theme packages | 0 | 0 (`test_stock_controls_only.py`, `test_no_global_stylesheet.py`, `test_app_styling_only_shrinks.py` unchanged or tighter) |
| Colours outside the meaning table and the series table | 0 | 0 |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-043A](completed/EPIC-043A_verify_dark_scheme.md) | Verify: every mode under the dark scheme at 1366×768 | Elite | None | 🟢 | ✅ Done (2026-10-20; pull request open) |
| [EPIC-043B](completed/EPIC-043B_options_colour_scheme.md) | Option A: the colour scheme is chosen in Tools → Options, and the series colours are contrast-checked in both schemes | Elite | 043A | 🟡 | ✅ Done (2026-10-20; pull request open) |
| [EPIC-043C](incomplete/EPIC-043C_pnl_tones_and_state_badges.md) | B1 + B2: PnL toned everywhere, and state badges | Elite | 043B, BOT-209 merged (the Plan dock structure) | 🟡 | Planned |
| [EPIC-043D](incomplete/EPIC-043D_headline_figures_and_tick_flash.md) | B3 + B4: headline figures, and the tick flash toggle | Elite | 043C | 🟡 | Planned |
| [EPIC-043E](incomplete/EPIC-043E_risk_tones_and_icons.md) | B5 + B6: risk tones and Lucide icons | Elite | 043D | 🟡 | Planned |

`043A` is read-only evidence and may shrink `043B` to the Options switch alone (PRO-009 §4). Each code child is its own pull request with its own reviewer.

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 Verify and choose | `043A` and `043B` merged: every mode read in the dark scheme; Options offers System, Light, Dark | Frames at 1024×700, 1366×768, 1920×1080 in both schemes; conformance suite green at all three sizes; the three guards unchanged or tighter |
| 2 Financial language | `043C`–`043E` merged | Every screen readable in light, dark and Windows High Contrast (the High Contrast session on a real Windows host is Not run until the owner does it); a before/after frame per touched screen |

## 5. Out of scope
- A brand, custom-drawn widgets, any style sheet, a third-party theme package, card layouts and fixed sizes (option C, rejected).
- Animations beyond the tick flash.

## Notes (newest first)
- **2026-10-20** — `043B` done: Tools → Options → Appearance (System, Light, Dark) applied through `setColorScheme`; nine series colours moved to read on white and dark. **Deviation from PRO-009 §2 A, for the owner to veto:** one value per colour serving both schemes, not one alternative per scheme, because series colours are read once at build time by ~24 sites (reason in `043B` §3).
- **2026-10-20** — `043A` done: every mode reads in dark and the chart chrome follows a runtime palette switch; `setColorScheme` has no effect on Qt's offscreen, minimal and xcb platforms (only a Windows or macOS host can show it), so `043B` tests the call and the owner's host judges the look.
- **2026-10-20** — Scaffolded after the owner accepted PRO-009; the documentation pull request also amends `EPIC-033` D8 and HLD §11.4.
