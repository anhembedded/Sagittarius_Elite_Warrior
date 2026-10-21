# BUG-252 — `test_a_restart_sends_nothing_again_and_tells_a_fill_missed_while_closed_once` failed in CI's `gate (Rest)` with two messages where it expects one

- **Reported:** 2026-10-21 (the author session of PR #674, from the first `gate (Rest)` run on that PR's docs-only head; the coordinator asked for the record and the fix)
- **Severity:** 🟢 P3 — a green change failed the required `-Full` check once; each such failure costs a ten-minute re-run cycle and, where re-runs are unavailable, a blocked merge. No product behaviour is wrong.
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** seven Discord journeys over the booted app (one in bots, six in alerting) counted every message sent, and the app's own heartbeat (first housekeeping pass, one second after start) landed beside the alert whenever a run took longer than a second; every journey now reads its posts through one shared helper that leaves the heartbeat out, pinned by a test per module that waits until the heartbeat has really been told.
- **Context:** CI and the test gate → `tests/integration/modules/bots/` and `tests/integration/modules/alerting/` (the Discord journeys over the booted app) → the alerting module's housekeeping thread (`src/modules/alerting/application/heartbeat_service.py`, `src/modules/alerting/adapters/threaded_delivery_host.py`)
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
The same count is made by the walking skeleton's six journeys (`tests/integration/modules/alerting/test_a_halted_bot_reaches_discord.py`: `[post] = …`, `heads[1]`, and an outbox history that began with the heartbeat) through `skeleton_world.py` → `Skeleton.wait_for_posts`, which counts every post. Found by the reviewer of the first version of this fix, which had only repaired the bots module: with a 1.5 s delay all six failed the same way.
Which net was silent: the gate was green because the race only loses when a runner is slow, and no test made the heartbeat arrive on purpose. The first version of this record said the blind spot "exists only in this module" and the author's sweep read "no mention of the heartbeat" as "handled"; the second was wrong (no mention means no handling).

## Fix
One shared helper, `tests/discord_posts.py`: `is_heartbeat` (its title is the alert kind's label, `label_of(AlertKind.HEARTBEAT)`, so a bot's alert cannot match), `posts_without_heartbeat` and `wait_until_the_heartbeat_is_told`. The bots journeys' `_settled` and flags assertion, and the skeleton world (`Skeleton.posts`, which `wait_for_posts` and the six journeys read, and the stalled-feed journey) read through it; the halted journey's outbox history leaves the heartbeat row out. The heartbeat and the housekeeping thread are untouched: the journeys must keep running the real composed app, so filtering, not standing the thread down. Sweep of every other read of a transport's `posts`: unit tests boot no app (no housekeeping thread); the heartbeat's own journey wants it; the Telegram and dead man's switch journeys check only a URL or chat id the heartbeat shares; one read is a read-only copy whose alerting never runs.

## Regression test
One per module, each waiting (on what was sent, not a sleep) until the heartbeat has really been told:
- `tests/integration/modules/bots/test_a_bot_tells_discord_about_every_fill_cycle_and_exit_on_the_fake_exchange.py::test_the_apps_own_heartbeat_is_not_counted_among_the_messages_a_bot_earns`: red before the fix with the CI error (`ValueError: too many values to unpack (expected 1)`), green after.
- `tests/integration/modules/alerting/test_a_halted_bot_reaches_discord.py::test_the_apps_own_heartbeat_is_not_one_of_the_posts_a_journey_counts`: red with `Skeleton.posts` unfiltered (the journey took `Heartbeat: 0 bot(s)` for its own post), green with the helper.
A throwaway probe with a 1.5 s delay after setup in every skeleton journey failed on the unfixed code (the reviewer's run: 6 of 8) and passes after (9 passed); the original restart journey with a 2.5 s delay likewise.

## Case study
None, for this reason: the blind spot (a count of everything sent on a booted app) was open in seven journeys of two modules, and one helper now closes it in all of them. What stops it coming back is the helper's docstring and a trap line (`pitfalls/tests.md` §8). A guard that no integration test reads `transport.posts` directly was weighed and not built: four legitimate direct reads would need an allowlist, and it would catch no more than the trap line does for a journey that never imports the helper.

## Verification
The two bots files and the four alerting skeleton files: 22 passed, twice in a row; both delay probes pass (they fail on the unfixed code). Positive proof the mechanism ran: the regression test asserts that a heartbeat post exists (`no heartbeat was told`) before it asserts the bot's message is the only one counted. Commit tier and the full gate: see the pull request.
