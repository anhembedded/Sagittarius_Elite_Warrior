# EPIC-043 — The desktop app reads like a financial application, through the platform's colour scheme and one meaning table

- **Status:** ✅ Done (5/5) — 2026-10-21; scaffolded 2026-10-20. B5 is partly delivered: the live risk level is `BOT-215`; B6 is delivered, command icons included
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
| [EPIC-043C](completed/EPIC-043C_pnl_tones_and_state_badges.md) | B1 + B2: PnL toned everywhere, and state badges | Elite | 043B, BOT-209 merged (the Plan dock structure) | 🟡 | ✅ Done (2026-10-20; pull request open) |
| [EPIC-043D](completed/EPIC-043D_headline_figures_and_tick_flash.md) | B3 + B4: headline figures, and the tick flash toggle | Elite | 043C | 🟡 | ✅ Done (2026-10-21; pull request open) |
| [EPIC-043E](completed/EPIC-043E_risk_tones_and_icons.md) | B5 + B6: risk tones and Lucide icons | Elite | 043D | 🟡 | ✅ Done (2026-10-21; pull request open), partly: `BOT-215` |

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
- **2026-10-21** — `043E` done, and the epic with it, with one honest gap. The Grid editor's liquidation lines are toned per side by the guard's own severity; the Strategies "Armed" state, the Options venue state and the K-line inspector's Change cell join the language (a candle that closed where it opened has no colour: owner may veto). **One premise of PRO-009 did not hold:** the risk watch's current level is on no screen as a state (`GridRiskWatch.level` exists in memory, starts at `SAFE` before any reading, which is the claim `BOT-215` warns against; `WARN` reaches the Alerts history as a row whose Severity is a word without a tone, `CRITICAL` the Bots table as a halt), so showing it is a read model first (`BOT-215`). Command icons (B6) are delivered: every non-checkable toolbar command of the five modes names an existing Lucide icon, and the mode toolbars already draw text beside it (`ModeHost.add_command`, `BOT-164`); an earlier version of this note said the Engine would draw the icon alone, which was wrong. **Measured against §2** (2026-10-21, `137fe0a6` plus this change): profit and loss are toned by `Tone` in the backtesting, bots and trading modules (25 files under `src/modules` import `meaning_colours`, 8 backtesting, 10 bots, 7 trading: `grep -rlE "import.*meaning_colours|meaning_colours import" src --include=*.py | grep ^src/modules/`; 23 name `Tone`: `grep -rlE "\bTone\b" src/modules --include=*.py`); the colour scheme is chosen in Tools → Options (System, Light, Dark); `043A` read every mode in dark at three sizes; no `QApplication` style sheet, palette or theme package (the three styling guards are unchanged and green; the one per-widget palette, in the monthly-returns heatmap, predates the epic); no hex colour literal in `src/` outside `series_colours.py`. Not run: a real Windows High Contrast session.
- **2026-10-21** — `043D` done: each Trade desk has a headline row (account value, unrealized PnL, open positions, nearest liquidation; Spot has the account value alone) set larger than the detail, and the Market watchlist's price can flash on a tick, an Options toggle off by default. **Deviation, for the owner to veto:** no "today's PnL", because nothing in the application reads a profit made today; it is a later use case. It also fixed a 043C slip: a tone on a label inside a toolbar was not drawn (the label draws with `ButtonText`).
- **2026-10-20** — `043C` done: profit, loss and change read with an arrow, a sign and a tone in every table, read-out and the Plan dock; bot and connection states are an icon and a word; `BOT-196` delivered inside it. A Watchlist change of exactly zero no longer reads as a win (owner may veto).
- **2026-10-20** — `043B` done: Tools → Options → Appearance (System, Light, Dark) applied through `setColorScheme`; nine series colours moved to read on white and dark. **Deviation from PRO-009 §2 A, for the owner to veto:** one value per colour serving both schemes, not one alternative per scheme, because series colours are read once at build time by ~24 sites (reason in `043B` §3).
- **2026-10-20** — `043A` done: every mode reads in dark and the chart chrome follows a runtime palette switch; `setColorScheme` has no effect on Qt's offscreen, minimal and xcb platforms (only a Windows or macOS host can show it), so `043B` tests the call and the owner's host judges the look.
- **2026-10-20** — Scaffolded after the owner accepted PRO-009; the documentation pull request also amends `EPIC-033` D8 and HLD §11.4.
