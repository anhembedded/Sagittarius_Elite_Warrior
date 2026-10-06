# BUG-165 — An empty Bots mode reads as one undivided black area: the empty panels have no boundary lines

- **Reported:** 2026-10-06 (the owner, in chat, with a screenshot of the Bots mode, Windows 11, dark theme: "những vùng này, bạn thấy thiếu đường ranh giới không, tui muốn có xíu")
- **Severity:** 🟢 P3 — cosmetic; with no bot, the Bots list, chart, Plan, Strategies and Orders cannot be told apart
- **Status:** ✅ Fixed (2026-10-06)
- **Board:** Empty panels (Bots, chart, Plan, Strategies, Orders …) were bare `QLabel`s with no frame and no `Base` background, so on Windows 11's flat docks they merged into the window. Cause: every empty page was built by hand as a bare label, and the Engine's `EmptyStateStack` builds its own. Fixed once in `support/ui_kit/empty_page.py` (the frame and `Base` role of a stock `QTableView`); every site goes through it, held by `tests/unit/support/ui_kit/test_empty_pages_are_framed.py`.
- **Context:** Use a bot (`Docs/SPEC/`, Bots mode) → `modules/bots/ui/bots_screen/`, `modules/trading/ui/`, `modules/market_data/ui/`, `support/ui_kit/` → `ui/` layer
- **Environment:** Windows 11, dark theme (the owner's desktop). Reproduced here on Linux/Fusion (light) under `xvfb-run`; the Windows 11 style cannot run here. App at `e631a0b`, engine at `engine.ref` `31a523e`.

## Reproduction
1. Start the app with no bots and trading off; open the Bots mode.
2. Look at the Bots, chart, Plan, Strategies and Orders panels.

**Expected:** each panel has a thin edge, like a filled table has.
**Actual:** only the instruction text shows; no edge, no panel background, so the panels read as one area. Every time.

## Symptom
The owner's words above; the same mode here, before: [`BUG-165_before.png`](BUG-165_before.png). The panels' titles float over unbroken background; the instructions sit in it.

## Root cause
An empty panel is not a view: it is a bare `QLabel`, which has `NoFrame` and no autofilled `Base` background, while a filled panel is a `QTableView`/`QScrollArea` with `StyledPanel | Sunken` and a `Base` viewport. On a style that draws docks flat the label has no edge to show. Twelve sites build such a page, each by hand:
- `src/support/ui_kit/spec_table.py:77` — `EmptyStateStack` (Engine) makes its own `QLabel` as page 0; every table of the app (Bots, Strategies, Orders, Fills, Watchlist, …) goes through it.
- `src/modules/bots/ui/bots_screen/bots_view.py:279` (`_note`) — the chart and Backtest placeholders.
- `src/modules/bots/ui/bots_screen/bot_plan_panel.py:86` — the Plan placeholder.
- `src/modules/trading/ui/trade/trade_view.py:73` — "No trading venue is enabled".
- `src/modules/trading/ui/market/market_view.py:113` — "no chart".
- `src/modules/trading/ui/desk/account_tabs/history_panel.py:72` — the history page's reading/error/empty page.
- `src/modules/market_data/ui/data_management_widgets/database_status_panel.py:147` — the database status instruction.

The fix is at one mechanism, `support/ui_kit/empty_page.py`, and needs no Engine change: `QLabel` is a `QFrame`, so the Engine's page is framed from the app through `stack.widget(0)`. No style sheet, no colour, no palette override: a frame shape and a palette *role*, which `test_stock_controls_only.py` and `test_app_styling_only_shrinks.py` do not count (they count style sheets, hand sizes, colour literals, the removed `Palette` module). The gate was silent because nothing held an empty page's look; no case study (not a blind spot of an existing net).

## Fix
- New `src/support/ui_kit/empty_page.py`: `frame_like_a_view` (`StyledPanel`, `Sunken`, `setBackgroundRole(Base)`, autofill), `empty_page(text, object_name)` (centred, wrapping, framed) and `frame_instruction_page(stack)` for the Engine's stack.
- `SpecTable` frames its stack's instruction page; the six hand-built labels above now call `empty_page`. The chart and Backtest placeholders are now centred like the others.

## Regression test
`tests/unit/support/ui_kit/test_empty_pages_are_framed.py` — 12 parametrised sites (Bots list, chart, plan, backtest, strategies, orders, fills; Trade no venue; Market no chart and watchlist; order history; database status). Each page's frame shape and shadow equal a fresh `QTableView`'s (`StyledPanel`, `Sunken`), its background role is the view's viewport role (`Base`), the background is autofilled, and it has no style sheet and no palette override. Red before the fix (12 failed, `frameShape` `NoFrame` ≠ `StyledPanel`); green after.

## Verification
- Regression test: 12 failed before, 12 passed after; `tests/unit/modules/bots`, `…/trading/ui`, `…/market_data/ui`, `tests/unit/architecture`: 2297 passed.
- Pictures from `scripts/workbench_desktop_e2e.py` under `xvfb-run` (Linux, Fusion, light theme): before [`BUG-165_before.png`](BUG-165_before.png), after [`BUG-165_after.png`](BUG-165_after.png) — each panel has its own edge and `Base` background.
- Not verified: the Windows 11 dark look itself (no such session here); the roles are the theme's, so it follows the owner's theme.
- Full gate: GitHub Actions' `ci-local.ps1 -Full` on the PR head (see the PR).
