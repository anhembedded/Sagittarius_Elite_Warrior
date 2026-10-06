# BUG-156 — The "Trading is OFF. Data view only." banner takes a full-width strip and does not read as a desktop app

- **Reported:** 2026-10-06 (the user, in chat, with one screenshot)
- **Severity:** 🟢 P3 — vertical space lost in every mode that shows the banner; no function is blocked
- **Status:** ✅ Fixed (2026-10-06)
- **Board:** Root cause: the composition root registered one banner factory that built a full-width strip for every run, including the resting "Trading is OFF" state that the window title and the status bar's venue label already state (HLD §11.2.2). Fixed by `environment_banner_factory`: no strip for the calm (INFO) state, the unhideable strip kept for testnet and venue mismatches.
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
`src/presentation/ui/app_bootstrapper.py` registered `lambda: EnvironmentBanner(banner_content)` as the surface banner factory, so every mode of every run got a strip across the window, whatever the content's severity. For trading off (`VenueAlignment.TRADING_DISABLED`, severity INFO, `environment_banner_content.py`) the strip says only what `MainWindow._show_venue` already says in two places a desktop app keeps its mode: the window title and a permanent status-bar label (`workbench::venue`). HLD §11.2.2 names those two as where "the venue in text" lives and says they replace the coloured banner of `EPIC-021K`; the strip was left over, and it cost a row of height in every mode.

## Fix
`environment_banner_factory(content)` (`support/ui_kit/environment_banner/environment_banner_factory.py`) answers a factory that builds no strip for an INFO content and a banner otherwise; the bootstrapper registers it. `WorkbenchSurface` accepts a factory answering `None` (`BUG-157`'s commit). Trading off therefore shows the title and the status label only. Testnet funds and the venue mismatches keep their strip, which is the surface's menu widget: no toolbar menu lists it and no layout holds it (`BUG-154`, `BUG-157`), so the user cannot switch it off.

**Decision for the owner:** this keeps the strip for the two situations that can lose money. HLD §11.2.2 goes further and would drop the strip for every severity, leaving the title and status bar. Recommendation: keep as is until a mismatch has been seen in use; removing the rest is `environment_banner_factory` answering `lambda: None` and nothing else. The status-bar label can be hidden with View → Status bar; the title cannot.

## Regression test
`tests/unit/support/ui_kit/environment_banner/test_environment_banner_factory.py`: a surface built under the trading-off factory has no strip, and one built under each other `VenueAlignment` (parametrised over the enum) has an `EnvironmentBanner`. With a factory that always builds the strip, the trading-off test fails (`menuWidget()` is an `EnvironmentBanner`, not `None`); with the fix it passes.

## Verification
- Positive proof, the real `MainWindow` over the booted engine: trading off, 0 strips in the 5 modes, title "Sagittarius Elite Warrior — Trading is OFF. Data view only.", the status label shown with the same text; testnet, 5 strips.
- Commit tier (`ci-local.ps1 -SkipTests`) and the banner, status-bar and architecture tests: see the pull request.
