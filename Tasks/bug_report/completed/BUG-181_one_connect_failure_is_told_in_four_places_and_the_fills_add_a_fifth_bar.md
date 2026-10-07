# BUG-181 — One refused key is told in four places on the Bots screen, and the fills it also refuses raise a second bar

- **Reported:** 2026-10-07 (the owner's screenshot of the Bots mode, a bot on Spot Testnet whose key the exchange refuses with `-2015`)
- **Severity:** 🟡 P2 — the same paragraph of advice four times buries the one thing to do, and a second bar for the same cause reads as two problems
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** The Connect failure's advice ("The exchange does not accept this API key…") sat in the message bar, the identity strip, the chart's place and the Plan's Connect item, and the fills read the same refusal failed into a second bar. Cause: each surface wrote `failure_cause()` itself, and the fills read raised an exception the screen could not tell from any other. Fix: the advice is the bar's alone, the other surfaces say "Not connected: key refused", and a refused fills read is handed to the Connect step.
- **Context:** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → Bots (`src/modules/bots/`) → `ui/bots_screen/` and `application/` (+ `trading/adapters/binance/history_reads.py`)
- **Environment:** the owner's Windows run on master `ffe2458`; reproduced here on the Bots screen's real wiring with the verified fakes, and on the composed app over the fake Binance server (`-2015` for a refused key). No real exchange was called.

## Reproduction
1. A bot on Spot Testnet whose key the exchange answers `-2015` for.
2. Select the bot. Expected: one message bar says what failed and what to do; the other surfaces say the state. Actual: the sentence "The exchange does not accept this API key. A testnet key does not work on mainnet… Retry venue account." appears in the bar, under it in the strip, in the centre of the chart area and in the Plan's Connect item, and a second bar, "The fills of this bot could not be read", appears.

## Symptom
On master, `tests/unit/modules/bots/ui/bots_screen/test_one_connect_failure_one_paragraph.py` counted the advice for each failure kind over everything the screen shows: it was in the bar, the strip, the chart's place, the Plan's Connect item and Start's reason, where the rule says once.

## Root cause
- `connect_view.failed_view` put `failure_sentence()` (advice + "Then choose Bots → Retry venue account") in `ConnectView.detail`, which the strip and the chart's lock (`lock_reason`) show, and `failure_cause()` in `ConnectView.cause`, which becomes the Plan's Connect item (`connection_read`) and Start's reason; `ConnectStep._failed` put the same advice in the bar. Four surfaces, one text, each by its own call: nothing said which of them owns the advice (`ui-presentation-rule.md` §10, `BOT-169`).
- The fills read (`GetBotFillsQuery`) raised `AccountHistoryUnavailableError` for the same `-2015`; `FencedReads` turns any exception into text, so `BotsFailures.read_failed` raised a bar under its own cause (`bots.read.fills`) next to the Connect bar (`bots.connect.spot_testnet`). The notifier merges two bars only when their technical texts match; they never do.

## Fix
- `connect_failure_words.py`: one short state per `ConnectionFailureKind` (`state_words`, `failure_state`), complete at import like the advice. `ConnectView` carries the state ("key refused") in `detail` and "Not connected: key refused" in `cause`; the chart's place reads "Spot Testnet: Not connected: key refused"; Start's reason and the Plan's Connect item use the same words (also in `bot_readiness_reader`). The advice stays in the bar only.
- The refusal is a value, not an exception: `AccountHistoryUnavailableError.kind` names a refusal the exchange names precisely (the same kinds as the connection check, `named_failure_kind`); `GetBotFillsQueryHandler` answers `BotFills.refused`; `BotsFailures.fills_answered` hands it to `ConnectStep.venue_refused` and shows "not read: key refused" in the fills panel. A step still reading or already failed says it itself; one that believed itself connected now fails, once, in its own bar. A failure the exchange does not name stays its own bar.

## Regression test
- `tests/unit/modules/bots/ui/bots_screen/test_one_connect_failure_one_paragraph.py::test_a_refused_connect_tells_its_advice_in_one_bar_and_only_there` (every kind of failure) — failed before the fix for the reason above (the advice on every surface, not once); passes after. The second test of the file pins the short words.
- `…/test_bots_failures.py` — a refused fills read raises no bar of its own; on a step that believed itself connected it becomes the Connect failure; a failure nobody named stays its own bar. These three use `AccountHistoryUnavailableError(kind=…)`, which master does not have, so on master they stop at that argument rather than at the behaviour: the paragraph test is the one that was red for the right reason.
- `tests/unit/modules/trading/adapters/binance/test_history_failures_name_their_kind.py` and `tests/integration/modules/bots/test_a_refused_fills_read_on_the_fake_exchange.py` — the real history reader over the fake server's `-2015` carries `KEY_REJECTED`.

## Verification
The Bots, trading, market-data and architecture suites and the commit tier on the pull request's head; see the pull request for the head commit and the CI run. Positive proof the new mechanism ran: the integration test above reads `-2015` over HTTP from the fake server and gets `BotFills.refused`.
