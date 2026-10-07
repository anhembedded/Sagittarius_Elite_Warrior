# BUG-168 — An exchange error page is rendered as a web page inside the Bots panel, and logged in full six times

- **Reported:** 2026-10-07 (the owner, chat, with a screenshot and the log of selecting a Spot Grid bot while the Spot Testnet answered `502 Bad Gateway`)
- **Severity:** 🟡 P2 — the panel shows a giant "502 Bad Gateway" heading and a horizontal rule instead of a sentence saying the exchange is unavailable; the log carries every HTML body in full
- **Status:** Open
- **Board:** Selecting a bot while the Spot Testnet answers an HTML error page shows that page, rendered as HTML, in the Bots panel ("502 Bad Gateway" as a heading), and logs the whole page six times.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `src/modules/bots/` → `ui/bots_screen/` (the status label); `src/modules/trading/adapters/binance/` (the error text)
- **Environment:** the owner's Linux desktop (Wayland), `master-warrior` after PR #409; Spot Testnet returning `502 Bad Gateway` from nginx.

## Reproduction
1. Have the Spot Testnet return an HTML error page (it did on 2026-10-07: maintenance, then `502 Bad Gateway`).
2. Open the Bots mode and select a Spot Grid bot.
3. Expected: one plain sentence, for example "Spot Testnet is unavailable (502 Bad Gateway). Try again later.", and one log line per failed read.
4. Actual: the status label reads "Could not read the planner: APIError(code=0): Invalid JSON error message from Binance:", followed by the page rendered as HTML (a large "502 Bad Gateway" heading, a rule, "nginx"). Each of four failed queries logs the whole HTML body, and two screen warnings log it again.

Frequency: every selection while the exchange answers HTML.

## Symptom
The owner's screenshot shows the Bots panel with "502 Bad Gateway" as a heading over the bots table. Log (abridged):
```
App - ERROR - GetSymbolOrderRulesQuery failed: APIError(code=0): Invalid JSON error message from Binance: <html>
<head><title>502 Bad Gateway</title></head> … <!-- a padding to disable MSIE and Chrome friendly error page --> ×6
App - ERROR - GetPlannerMarketQuery failed: … (same page)
App.Bots.Screen - WARNING - Bots screen read planner (s8nh27) failed: … (same page)
App - ERROR - GetOrderHistoryQuery failed: Spot order history could not be read: … (same page)
App - ERROR - GetBotFillsQuery failed: … (same page)
App.Bots.Screen - WARNING - Bots screen read fills (s8nh27) failed: … (same page)
```

## Root cause
Established in part; the full mechanism is not yet traced.
- **Rendering:** the status label is a bare `QLabel()` (`src/modules/bots/ui/bots_screen/bots_view.py:114`) with no `setTextFormat`. A `QLabel` defaults to `Qt.AutoText`, which renders any text that looks like HTML as rich text. No `src/` file calls `setTextFormat` at all (53 bare `QLabel()` in `src/`), so the same can happen wherever a label shows an exception's text.
- **Text:** python-binance turns a non-JSON answer into `BinanceAPIException(code=0)` whose message carries the whole response body. The adapters pass `str(exc)` upward, and the screen shows it verbatim. `BUG-167` built one Binance error classifier (`src/modules/trading/adapters/binance/connection_failure.py`), but it serves the connection check only; the queries above do not go through it.
- **Logging:** each layer that fails logs the full message, so one outage writes the page six times. That breaks `logging-rule.md` §4 (one line per operation).

## Fix
Not yet done.

## Regression test
Not yet written.

## Verification
Not run.

## Suggested next steps
- Classify a non-JSON Binance answer once, at the adapter boundary: an "exchange unavailable" failure carrying the HTTP status and the page title, never the body. `EPIC-034D` plans a `MAINTENANCE` kind on the same path.
- Show exception text as plain text everywhere: a guard that every `QLabel` showing dynamic text uses `Qt.PlainText`, or a shared helper that does it.
- Log the body once at DEBUG, and one ERROR line per failed operation.
- Where the message is shown (inline, banner or dialog) is `BOT-169`'s decision.
