# BUG-197 — `test_the_chart_and_every_panel_follow_the_selection` fails intermittently under `-n 4`: another test leaves the `App` logger at INFO

- **Reported:** 2026-10-09 (the coordinator session, from `pytest tests/unit tests/integration -n 4`)
- **Severity:** 🟢 P3 — a flaky gate test; no user-facing effect
- **Status:** Open
- **Board:** The Bots selection test failed on some xdist workers because `test_bug042_…` leaves the `App` logger at INFO, which lets the chart's load lines into the bot log.
- **Context:** Test infrastructure → `tests/conftest.py`; Bots screen log (`src/modules/bots/ui/bots_screen/bot_chart_host.py`, `bot_log_feed.py`)
- **Environment:** Linux, Python 3.12, pytest-xdist `-n 4`; engine at `engine.ref`.

## Reproduction
Same process, the leaking test first (what an xdist worker does when it draws both):
`pytest tests/unit/modules/backtesting/domain/test_bug042_paper_exchange_log_level.py tests/unit/modules/bots/ui/bots_screen/test_bots_selection.py`
Alone, or with `tests/unit/modules/bots`, the selection test passes.

## Symptom
```
>       assert view.log.toPlainText() == "Bot a00001 placed level 3"
E       AssertionError: assert 'Bot a00001 p... for BTCUSDT.' == 'Bot a00001 placed level 3'
```

## Root cause
`tests/unit/modules/backtesting/domain/test_bug042_paper_exchange_log_level.py:109` calls `logging.getLogger("App").setLevel(logging.INFO)` and never restores it. The chart reports its load through `BotChartHost._on_chart_said` (`bot_chart_host.py:143`), which logs at INFO on `App.Bots.Chart`; `BotLogFeed` copies INFO+ `App.Bots` records into the bot's log (`bot_log_feed.py`). With the `App` level unset the INFO records are dropped (the test saw only its own line); on a worker that ran the leaking test first they arrive synchronously (the held pool runs the load on the test thread), so the log holds the chart lines too. Not a timer or thread race, and not a production defect: showing the chart's load on the bot's log is the intended `EPIC-034A` behaviour.

## Fix
- `tests/conftest.py`: an autouse fixture gives the `App` logger's level back after every test, closing the leak for every test.
- `test_bots_selection.py`: the test pins `App.Bots` to INFO itself (the level it depends on) and asserts the bot's own line first, then only that bot's chart lines.

## Regression test
`tests/unit/modules/bots/ui/bots_screen/test_bots_selection.py::test_the_chart_and_every_panel_follow_the_selection` — red before the fix with the leaking test run first (the assertion above), green after, in either order.

## Verification
Before: red as above. After: the same two-file command passes, a probe test run after the leaking test sees the `App` level back at NOTSET, and `tests/unit/modules/bots` + `tests/unit/modules/backtesting/domain` pass under `-n 4`.
