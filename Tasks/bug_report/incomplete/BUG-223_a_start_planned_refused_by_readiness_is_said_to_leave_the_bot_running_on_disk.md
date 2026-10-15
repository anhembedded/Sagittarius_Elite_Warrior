# BUG-223 — A bot refused by `--start-planned` for a missing key was later found RUNNING on disk

- **Reported:** 2026-10-15 (the owner's VPS, `run --start-planned --confirm-venue spot_mainnet`)
- **Severity:** 🟡 P2 — on the real-money path a bot that never traded would be recovered, skipped by `--start-planned` and called "already running" by the plan diff
- **Status:** Open
- **Board:** Bot 44wa1x, refused `VENUE_NOT_READY` (no key), was found RUNNING on disk afterwards; the refusal path was traced and does not write it, so how it became RUNNING is not established.
- **Context:** Host start-up (`EPIC-038D`) → `src/modules/operations/`, `src/modules/bots/` → `application/use_cases/start_bot*`
- **Environment:** Linux VPS, headless; unit with no Spot Mainnet key.

## Reproduction
Not yet reproduced. On the composed app with the fake exchange and the Spot key removed, `StartPlannedBots` for a DRAFT bot logs the same `VENUE_NOT_READY (1 thing left: …: Not connected: no API key)` and the bot stays DRAFT on disk and across the next boot (`tests/integration/modules/bots/test_a_start_planned_refused_for_no_key_leaves_the_bot_at_rest_on_the_fake_exchange.py`, green today: a pin, not a regression of this report).

## Symptom
Journal of the run: `[start-planned] bot 44wa1x was not started: VENUE_NOT_READY …`, then `BOOTING -> SERVING`. Afterwards the read-only `bot apply plan.json --dry-run` printed `desired running: already running, nothing to start` (the diff's word for RUNNING, PAUSED or RECOVERING, `plan_differ.py:238`), and a writable `bot apply` logged `Restored bot 44wa1x: RUNNING -> RECOVERING`.

## Root cause
Not yet established. Traced and ruled out: `StartBotForHostCommandHandler.execute` dispatches `StartBotCommand`; `StartBotCommandHandler.execute` (`start_bot/handler.py:95-100`) returns the readiness refusal before any save; the only writers of STARTING/RUNNING are `BotRunner.start` (`bot_runner.py:82`, after `GridStartPreconditions.check` passes) and the executor's `BotRunState`. The desktop Start dispatches the same `StartBotCommand` (`bot_commands.py:101`), so it has the same order. Contradiction in the evidence: the host started the bot only because the status report showed it at rest (DRAFT/STOPPED), so something wrote RUNNING between that step and the dry-run, and nothing in the logs shows who.

## Fix
Pending a cause. No code change is justified by what was traced.

## Regression test
Pending (the pin above passes without a fix).

## Verification
Not run against the VPS.

## Suggested next steps
Collect from the VPS: the bot's JSON file and its mtime (state, `run_started_at`, runtime reason), the whole journal of that unit between the refusal and the stop (`grep -E 'bot-transition|44wa1x'`), and whether another process (a desktop copy, an earlier `run` with a key, a second unit) held the data root. A `[bot-transition]` line for 44wa1x showing `START`/`STARTING` names the writer.
