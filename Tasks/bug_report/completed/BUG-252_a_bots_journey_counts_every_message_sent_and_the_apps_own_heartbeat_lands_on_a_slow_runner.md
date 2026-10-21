# BUG-252 — `test_a_restart_sends_nothing_again_and_tells_a_fill_missed_while_closed_once` failed in CI's `gate (Rest)` with two messages where it expects one

- **Reported:** 2026-10-21 (the author session of PR #674, from the first `gate (Rest)` run on that PR's docs-only head; the coordinator asked for the record and the fix)
- **Severity:** 🟢 P3 — a green change failed the required `-Full` check once; each such failure costs a ten-minute re-run cycle and, where re-runs are unavailable, a blocked merge. No product behaviour is wrong.
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** a bots journey counted every Discord message sent, and the booted app's own heartbeat (first housekeeping pass, one second after start) landed beside the bot's fill whenever the run took longer than a second; the journeys now read what a bot earned, without the heartbeat, pinned by a test that waits until the heartbeat has really been told.
- **Context:** CI and the test gate → `tests/integration/modules/bots/` (the Discord journeys on the fake exchange) → the alerting module's housekeeping thread (`src/modules/alerting/application/heartbeat_service.py`, `src/modules/alerting/adapters/threaded_delivery_host.py`)
- **Environment:** GitHub Actions `ubuntu-latest`, Python 3.12.15, `gate (Rest)`. PR #674 head `bea05ea857a6d27c11a2f0e8c3d74a930f70e93c`, run 39560297277, job 119089667883, attempt 1. Local container: Linux, Python 3.12.

## Reproduction
Deterministic once the run lasts a second; not reproduced on a fast machine.
1. Boot the app with a fake Discord transport and the fake exchange (`_told`), start a grid bot, move the price so one buy fills.
2. Let one second pass before the journey reads what was sent (a slow runner does this by itself; a `time.sleep(2.5)` after `move_price` does it here).
3. Expected: one message, the fill. Actual: two, the fill and `INFO · Heartbeat: 1 bot(s)`; `[told_before] = _settled(...)` raises `ValueError: too many values to unpack (expected 1)`.
Frequency: one failure in the CI history seen by this session; the same test passed on the same code on the previous head (`0e3c4e69`) and 6 of 6 times locally.

## Symptom
From the job log of run 39560297277, job 119089667883 (`gate (Rest)`):
```
[gw1] [  6%] FAILED Sagittarius_Elite_Warrior/tests/integration/modules/bots/test_a_bot_tells_discord_about_every_fill_cycle_and_exit_on_the_fake_exchange.py::test_a_restart_sends_nothing_again_and_tells_a_fill_missed_while_closed_once
FAILED ...::test_a_restart_sends_nothing_again_and_tells_a_fill_missed_while_closed_once - ValueError: too many values to unpack (expected 1)
  ❌  Tests FAILED
  ✅  Run log — no WARNING/ERROR/CRITICAL log records, nothing uncollectable
```
With the 2.5 s delay, the posts the probe printed were `['🔵 **INFO · Order filled: grid** …', '🔵 **INFO · Heartbeat: 1 bot(s)** …']`.

## Root cause
At `ee768d8`. The booted app starts a housekeeping thread that wakes every second (`src/modules/alerting/composition/alerting_bindings.py:161` `HOUSEKEEPING_SECONDS = 1.0`, waited on in `src/modules/alerting/adapters/threaded_delivery_host.py:112`). Its first pass sends a heartbeat because none is stored (`src/modules/alerting/application/heartbeat_service.py:121`, `last is None`), as `EPIC-036E` (#653, 2026-10-21) designed. The journey's reader `_settled` returns every post on the transport (`tests/integration/modules/bots/test_a_bot_tells_discord_about_every_fill_cycle_and_exit_on_the_fake_exchange.py:141`) and one assertion counts the flags of all of them (line 201), so the number of messages it sees is the bot's plus however many heartbeats the run lasted long enough to earn: zero on a fast machine, one on a slow one. The journey was written when no heartbeat existed (2026-10-19) and passed since only because its body takes less than a second. The alerting journeys that boot the same app already ignore the heartbeat (`_kinds` in `test_the_composed_app_delivers_alerts.py`); this module did not. Not a defect of the heartbeat: it is meant to arrive on its own.
Which net was silent: the gate was green because the race only loses when a runner is slow; no test made the heartbeat arrive on purpose. No case study: the blind spot (a count of everything sent on a booted app) exists only in this module, and the fix closes it.

## Fix
`_posts_about_bots` (same file) is what the channel was sent without the heartbeat (`_is_heartbeat`: its title is the alert kind's label, `label_of(AlertKind.HEARTBEAT)`); `_settled`, which the exit journey also imports, and the flags assertion read it. The heartbeat itself is untouched and the journeys still wait on the outbox emptying. The other two reads of `transport.posts` are unaffected (one filters by title, one is a read-only copy whose alerting never runs). It filters rather than stands the thread down because the journeys must keep running the real housekeeping thread: a restart journey is about what the app tells, and the heartbeat is part of it.

## Regression test
`test_the_apps_own_heartbeat_is_not_counted_among_the_messages_a_bot_earns` (same file): `_until_the_heartbeat_is_told` waits, on what was sent and not on a sleep, until the heartbeat has reached the channel, then asserts the bot's one message and its one flag. Red before the fix for the CI reason (`ValueError: too many values to unpack (expected 1)`, now deterministic); green after. The original restart journey with a 2.5 s delay inserted (the slow runner) also failed before and passes after (a throwaway probe, not kept).

## Verification
The file and the exit journey: 12 passed, three runs in a row; the probe with a 2.5 s delay: 9 passed (it fails on the unfixed file). Positive proof the mechanism ran: the regression test asserts that a heartbeat post exists (`no heartbeat was told`) before it asserts the bot's message is the only one counted. Commit tier and the full gate: see the pull request.
