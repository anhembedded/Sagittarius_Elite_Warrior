# BUG-224 — `main.py bot stop <id>` on the headless host can never stop a Futures bot

- **Reported:** 2026-10-17 (owner, on the VPS with two Futures Testnet bots)
- **Severity:** 🟡 P2 — a Futures bot cannot be stopped from the command line; the desktop UI still can
- **Status:** ✅ Fixed (2026-10-17)
- **Board:** `bot stop` on a Futures bot was always refused. Cause: the host's stop carried KEEP for every bot, which a position venue refuses. Fix: `bot stop --close-position` carries CLOSE_AT_MARKET through the command file; without it a Futures stop is refused in words naming the flag
- **Context:** [SPEC-015](../../../Docs/SPEC/SPEC-015_run_the_bots_headless.md) → `src/modules/bots/` → `application/use_cases/stop_bot_for_host`, `stop_bot_for_operator`
- **Environment:** Linux VPS, `main.py run` host, Futures Testnet, two bots; build at `0889c02`.

## Reproduction
1. Run the host with a RUNNING Futures Testnet bot.
2. From a second shell: `main.py bot stop <id>`.
3. Expected: STOPPING then STOPPED. Actual: exit 2, nothing changes.

## Symptom
`Futures positions are not kept when a bot stops: this app places no stop on the exchange yet, and a leveraged position with no stop can be liquidated. Stop and close the position.` The Bots tab's Stop works because it offers "Close the position at market".

## Root cause
At `0889c02`, `src/modules/bots/application/use_cases/stop_bot_for_host/handler.py:39` always dispatched `StopBotCommand(bot_id, ExposureHandling.KEEP)`, and `StopBotCommandHandler._keep_refusal` (`stop_bot/handler.py:68-80`, test `keep_on_stop_closed_reason` in `contracts/venue_profile.py:180`) refuses KEEP on a position venue (`EPIC-039H`). The command line had no way to choose the other member of `ExposureHandling`. Its tests were Spot-only or used a recording dispatcher (`test_stop_bot_for_operator.py::test_a_position_venue_is_left_to_the_screens_refusal...` asserted the doomed `StopBotForHostCommand`), so the refusal the real chain returns never ran.

## Fix
Owner decision (option B): the choice travels from the operator to the screen's Stop. `--close-position` (a `store_true` of `bot stop`, `cli_commands.json`) → `HostControlRequest.close_position` → the command file's optional `close_position` key (`sew.host-command/1`, written only when true, so an unchanged command is the document an older host reads; refused on any action but stop) → `StopBotForOperatorCommand.close_position` → `StopBotForHostCommand.exposure` → the screen's `StopBotCommand`. A position venue without the flag is refused in words that say the command closes the position at market and name the flag. With the flag the exposure is `ExposureHandling.CLOSE_AT_MARKET`, the member the screen's close dialog uses (no new close path). Spot without the flag keeps (KEEP); with it, sells, as the screen does.

## Regression test
`tests/unit/modules/bots/application/test_bot_stop_for_operator_on_a_position_venue.py` - the real operator, host and screen Stop handlers behind a routing dispatcher over a Futures bot. Before the fix the same call returned `EXPOSURE_MUST_CLOSE` with no way past it (reproduced from the test's world; the new tests failed on the missing field). Also the codec, executor, verb and host-handler tests.

## Verification
Commit tier green (ruff, format, mypy, reference check, architecture guards); 5324 tests of `tests/unit/{modules/bots,modules/operations,architecture}` green. Not run: a live Futures Testnet host.

## Family scan
- `bot pause` / `bot resume`: no exposure argument (`PauseBotForHostCommand`, `ResumeBotForHostCommand` take none), so no KEEP assumption.
- The host's shutdown stop (`--on-stop stop-bots`, `adapters/stop_bots_first.py:82`) dispatches `StopBotForHostCommand(bot_id)`, i.e. KEEP, and so also leaves every Futures bot (refused, listed as left). Not changed: closing positions unattended at shutdown is a real-money policy the owner has not decided; the runbook now says so.
