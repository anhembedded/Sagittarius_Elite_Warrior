# EPIC-010E — Database screen: symbol and interval

**Status:** ✅ Done 2026-08-26 — Elite
**Repo:** **Elite** — design §8 step 3
**Depends on:** `EPIC-010D` (same shape; do it second so the pattern is proven once)

## What

`DataManagementPresenter` implements the contributor contract, scope
`StateScope("data_management", None, PERSISTENT)`:

| Value | Today |
| :--- | :--- |
| Selected symbol | `_DEFAULT_SYMBOLS[0]` = `"BTCUSDT"`, hardcoded (`data_management_view_model.py:16, 80`) |
| Selected interval | `_SUPPORTED_INTERVALS[0]` — the first `TimeFrame` member (`:17, 81`) |

Deliberately **not** persisted here: `_search_text`, `_use_custom_time` and the
custom range. They are T2 or lower value, and this task exists to prove the
pattern on a second screen, not to maximise coverage.

## The wrinkle this screen has and the Dev Board does not

`_symbol_options` is **overwritten at runtime by DB auto-discovery**
(`data_management_presenter.py:102, 177, 306`). So a restored symbol can be
valid at restore time and then vanish, or vice versa.

Restore therefore validates against whatever the app currently knows, and a
symbol that is not (yet) in the options falls back to the default. It must not
error, and it must not wait for the scan.

## Restore causes no side effects (mode #12)

`_cbo_symbol.currentTextChanged` → `_on_symbol_text_changed`
(`data_management_view.py:302, 349-351`). Same rule as `010D`: write the
ViewModel, or use `QSignalBlocker`. **Opening the screen must not trigger a
scan or a sync.**

## Acceptance

- Pick a symbol + interval, quit, relaunch, open the screen → both restored
- Restoring does **not** kick off a DB scan or a sync
- A persisted symbol absent from the discovered options → falls back cleanly

## Note for `010H`

This screen and the Dev Board both **ignore** config's `DEFAULT_SYMBOLS` /
`DEFAULT_INTERVAL` and hardcode their own literals — only `BackTestPresenter`
reads config. Adding a persistence layer on top makes the three-level precedence
(`ui_state` > `user_config` > module constant) live without anyone having
defined it. Do not fix that here; it is `010H`, and the precedence order is
proposed in the first design's §7.
