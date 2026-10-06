# BUG-155 — New bot: the Venue list is empty yet required, and Symbol is a free-text field

- **Reported:** 2026-10-06 (the user, in chat, with two screenshots)
- **Severity:** 🟡 P2 — no bot can be created: Create bot stays disabled because no venue can be chosen
- **Status:** Open
- **Board:** New bot: the Venue list is empty and Create bot stays disabled, so no bot can be created; the user expects Venue to be optional and Symbol to be the symbol picker the other screens use. Not investigated yet.
- **Context:** [SPEC-014 Run a grid bot](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `src/modules/bots/` → New bot dialog, `ui/` layer
- **Environment:** Windows (the user's desktop). App commit, engine commit, Python version and the enabled venues not captured.

## Reproduction
1. Start the app and open the New bot dialog in the Bots mode.
2. Leave Kind on Spot Grid; open the Venue list.
3. Type a symbol (`BTCUSDT`) and a name (`asdas`).

**Expected (the user's words, translated):**
1. Venue: "the venue value cannot be entered; this value should not be required."
2. Symbol: "the symbol field should have a symbol-picker widget, like the other screens."

**Actual:**
1. The Venue list is empty. The dialog says "No Spot venue is enabled. Enable one in Tools > Options > Trading first." Create bot stays disabled with Symbol and Name filled.
2. Symbol is a plain text field with the placeholder "e.g. BTCUSDT".

**Frequency:** Not yet established (one occurrence reported). Not yet reproduced here.

## Symptom
- The user's words: "1. giá trị venue k nhập được, giá trị này ko nên bắt buộc. 2. chổ nhập symboy thì phải là có cái widget chọn symboy chứ, giông mấy màng hình khác đó".
- The dialog with the Venue list empty, Venue highlighted by the user: [`BUG-155_new_bot_venue_empty.png`](BUG-155_new_bot_venue_empty.png).
- The dialog with Symbol and Name filled and Create bot still disabled: [`BUG-155_new_bot_symbol_typed.png`](BUG-155_new_bot_symbol_typed.png).
- The dialog's own hint sends the user to Tools > Options > Trading, which in the same period fails with [BUG-154](BUG-154_tools_options_fails_on_a_deleted_trading_settings_page.md). Whether the two are related is not established.

## Root cause
Not yet established. The user asked for the report only; no investigation was done.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Record whether any Spot venue was enabled in the run, and the app and engine commits.
- Decide with the user whether a bot may exist without a venue (SPEC-014), and which symbol picker the dialog should reuse.
- Then follow `fix-bug-rule.md`.
