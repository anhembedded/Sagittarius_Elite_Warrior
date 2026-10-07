# BUG-168 — An exchange error page is rendered as a web page inside the Bots panel, and logged in full six times

- **Reported:** 2026-10-07 (the owner, chat, with a screenshot and the log of selecting a Spot Grid bot while the Spot Testnet answered `502 Bad Gateway`)
- **Severity:** 🟡 P2 — the panel shows a giant "502 Bad Gateway" heading and a horizontal rule instead of a sentence saying the exchange is unavailable; the log carries every HTML body in full
- **Status:** Fixed (2026-10-07)
- **Board:** Selecting a bot while the Spot Testnet answers an HTML error page showed that page, rendered as HTML, in the Bots panel and logged it six times. Cause: python-binance wraps a non-JSON answer's whole body in `BinanceAPIException(code=0)`, adapters forwarded that text, and every `QLabel` renders HTML-looking text (`Qt.AutoText`). Fixed: one classifier at the adapter boundary words it "the exchange is unavailable (HTTP 502 Bad Gateway)" (`MAINTENANCE` for the connection check), every label is made by `plain_label` (guarded), and a failed read is one line above DEBUG.
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
Three mechanisms, all established:
- **Text:** python-binance turns a non-JSON answer into `BinanceAPIException(code=0)` whose message is the whole response body (`binance/exceptions.py`). Six adapter sites forwarded it as `str(exc)` or `repr(exc)`: the market price reads (`market_price_reads.py`), both commission readers, the history readers (`history_reads.py`), the Futures account control (a `code=0` rejection with the page as its message) and — the one that reached the planner screen — both metadata providers (`futures_metadata_provider.py`, `spot_metadata_provider.py`), whose `refresh()` let the raw exception escape the port. `BUG-167`'s classifier served the connection check only.
- **Rendering:** a `QLabel` is `Qt.AutoText` and draws any string that looks like HTML as rich text. The status label (`bots_view.py:114`) was one of 102 bare `QLabel(...)` calls in `src/`.
- **Logging:** the engine's dispatcher (`sagittarius_engine/kernel/dispatcher.py:72`) already logs a failed query at ERROR, and `FencedReads._deliver` logged the same failure again at WARNING, so one outage wrote the page twice per read.

## Fix
- `connection_failure.py` is the one classifier. `is_non_json_answer` recognises the SDK's non-JSON exception; `describe_failure(exc)` words any failed exchange call as a short plain reason ("the exchange is unavailable (HTTP 502 Bad Gateway)": the status and the page's `<title>`, tags stripped and capped, never the body) and writes the page once, at DEBUG. `classify_connection_failure` names the same answer `ConnectionFailureKind.MAINTENANCE` (with its words in `connection_words.py` and the CLI formatter), so the connection check no longer logs it as an unclassified exception. `EPIC-034D` reuses both.
- Every adapter site above words its failure through `describe_failure`; the metadata providers raise `SymbolRulesUnavailableError` through `metadata_reads.catalog_read_failures`, which the planner handler already turns into a sentence.
- `src/support/ui_kit/plain_label.py` is the one way to make a `QLabel`: `Qt.PlainText`. All 102 call sites use it. `tests/unit/architecture/test_labels_show_plain_text.py` fails on a `QLabel(...)` call outside the factory, and on a `QLabel` subclass that never calls `setTextFormat` (the heatmap cell, markup on purpose, now says so).
- `FencedReads` logs a failed read at DEBUG: the dispatcher's ERROR is the one line per operation.
- Not changed, and why: `QMessageBox` static dialogs and tooltips also auto-detect markup. Neither shows exception text today; a future one that does needs the same treatment.

## Regression test
`tests/unit/modules/trading/adapters/binance/test_html_answer_is_classified_once.py` builds the real SDK exception from a 502 page and asserts, per adapter, that the error text carries the status and title and no markup; red before the fix (the classifier did not exist). `test_bots_view.py::test_the_status_line_shows_an_exchange_page_as_text_not_as_a_web_page`, `test_fenced_reads.py::test_the_screen_does_not_log_a_failed_read_a_second_time` and the guard's probes cover the label and the log.

## Verification
The new tests, the trading adapter, UI and CLI suites, the Bots screen suite and `tests/unit/architecture` pass. Positive proof the new mechanism ran: `test_the_page_is_logged_once_at_debug_and_never_above` observes the single DEBUG line `describe_failure` writes. Not reproduced against the live Spot Testnet (egress is blocked here).
