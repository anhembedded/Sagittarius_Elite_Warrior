# BUG-156 — The "Trading is OFF. Data view only." banner takes a full-width strip and does not read as a desktop app

- **Reported:** 2026-10-06 (the user, in chat, with one screenshot)
- **Severity:** 🟢 P3 — vertical space lost in every mode that shows the banner; no function is blocked
- **Status:** Open
- **Board:** A full-width "Trading is OFF. Data view only." banner under the toolbar costs vertical space and does not look like a desktop app; the user asks for a redesign. Not investigated yet.
- **Context:** Trading on/off state shown to the user → `shell/` and `src/modules/trading/` → workbench chrome, `ui/` layer
- **Environment:** Windows (the user's desktop). App commit, engine commit and Python version not captured. The Trade mode was shown with trading off.

## Reproduction
1. Start the app with trading off.
2. Open the Trade mode.

**Expected (the user's words, translated):** "this takes space and does not look like desktop-app UI; redesign this place, give another solution."
**Actual:** under the toolbar (Enable live trading, New order, Cancel all orders, Emergency stop, all disabled), a strip across the whole window width holds an info icon and "Trading is OFF. Data view only."; the area below it is empty.

**Frequency:** Every time trading is off (as reported). Not yet reproduced here.

## Symptom
- The user's words: "cái này tốn diện tích, mà nó ko giống UI destop app, hay desin lại chổ này, cho 1 giải phát khác."
- Screenshot, the strip outlined by the user: [`BUG-156_trading_off_banner.webp`](BUG-156_trading_off_banner.webp).
- The window title already reads "Sagittarius Elite Warrior — Trading is OFF. Data view only." ([BUG-154](BUG-154_tools_options_fails_on_a_deleted_trading_settings_page.md) screenshot).

## Root cause
Not yet established. The user asked for the report only; no investigation was done.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Proposed design, for the user to accept: drop the banner and show the state where desktop apps keep a persistent mode — a permanent status-bar indicator ("Trading: OFF", tooltip "Data view only", a click opens the enable action), alongside the window title that already carries it. The disabled toolbar actions explain themselves through their tooltips.
- Then follow `fix-bug-rule.md` and `ui-presentation-rule.md`.
