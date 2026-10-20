# ADR — The headless host leaves a Futures bot only while a stop on the exchange covers its position, and closes every other one before it exits

**Epic:** [EPIC-038](README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** 🤖 Agent decision, delegated by the owner (ONBOARDING §7). The owner delegated owner question O12 to the coordinator session on 2026-10-20 (*"bạn tự quyết định đi"*, translated: you decide), and the coordinator decided it as option (a) with a per-bot fallback; this record implements that decision and settles the points it left to the author (D4 to D6).
**Supersedes / superseded by (optional):** completes O12 of [`EPIC-039/DECISION_2026-10-10_futures_venue_profile.md`](../EPIC-039_futures_venue_profile/DECISION_2026-10-10_futures_venue_profile.md) §4a (accepted 2026-10-13: *"the stop policy is per venue profile; leave orders resting is not acceptable for a Futures bot without a protective stop"*), which [`DECISION_2026-10-16_futures_protective_stop_minimum.md`](../EPIC-039_futures_venue_profile/DECISION_2026-10-16_futures_protective_stop_minimum.md) made answerable by putting a stop on the exchange (`EPIC-039L` C2).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit §1 names |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context
Read at `0ccc921`. ✅ `LeaveOrdersResting` (`src/modules/operations/adapters/leave_orders_resting.py`) asked the exchange for nothing for every bot, so a `systemctl stop`, a `sew-update` or a restart left a Futures bot's position, ladder and stop as they were, whether or not a stop stood: the O12 answer was recorded but not implemented. ✅ `StopBotsFirst` sends `StopBotForHostCommand` with `ExposureHandling.KEEP`, which the screen's Stop refuses on a position venue (`keep_on_stop_closed_reason`, `EXPOSURE_MUST_CLOSE`), so under `--on-stop stop-bots` a Futures bot is refused and left. ✅ Since `EPIC-039L` C2 a Futures Grid keeps a `STOP_MARKET closePosition` stop on the exchange, recorded in its file and judged against the exchange's open orders by `ProtectiveStopService.describe_stop` for the halt's words (`stop_words`: "stands", "not on the exchange", "does not cover the position", "could not be read").

The forces: an upgrade or restart must not force-close every protected position (fees, slippage, a market exit per upgrade); a leveraged position with no standing stop must never be left unwatched; the whole stop must end within `--stop-timeout` plus `STOP_GRACE_SECONDS` (`TimeoutStopSec=62`).

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **Under `--on-stop leave-orders` (the unit's default) a Futures bot whose position a stop on the exchange covers is left as it is** - position, resting orders and stop stay - and comes back RECOVERING as today. | Accepted | 🤖 Agent decision, delegated by the owner | A restart or upgrade costs no market exit for a protected position. |
| D2 | **A Futures bot whose stop is missing, not on the exchange, on the wrong side, or cannot be read is closed before exit through the Stop the Bots tab uses** (`StopBotForHostCommand` with `ExposureHandling.CLOSE_AT_MARKET`: cancel the ladder, close at market, reduce-only). An unread stop is not a covering stop. Each such bot is named at WARNING in the log and kept in the stop ledger until it is STOPPED. | Accepted | 🤖 Agent decision, delegated by the owner | A leveraged position with no standing stop is never left unwatched; the same Stop path, no second way to close. |
| D3 | **Spot is unchanged**: its bots are left as they were, with no read of the exchange. The venue profile decides, in `bots` and nowhere else (`ExposureKind.POSITION`, `venue_profile.py`): the status read model carries it as `BotStatusEntry.may_hold_position`, and the policy decides on it **before** the read budget or a failed read can matter. | Accepted | 🤖 Agent decision, delegated by the owner | A Spot bot is never asked about and never closed: closing it at market would sell its base (review of #626, round 1, finding 1: past the budget an unread answer had closed Spot bots). Only a bot whose venue may hold a position is read, and for it an unread answer is closed. |
| D4 | **"Covered" is read fresh from the exchange, by the one reader the halt's words already use.** `StopCoverageReader` (`bots/application/kinds/grid/protection/`) judges the bot's recorded stops against the exchange's open protective orders and the position (`judge_stop`, extracted from `stop_words`); `describe_stop` and the new `IExposureProtection.read_coverage` are two renderings of it. The question travels `GetBotStopCoverageQuery` → `IBotRunner.stop_coverage` → `IBotExecutor.stop_coverage` → the bot's protection; the read does not queue behind the bot's worker. | Accepted | 🤖 Agent decision, delegated by the owner (P5: the existing reading, not a second one) | One definition of "the stop stands" for the halt and the host. A read that races a placement finds the stop missing and errs toward closing. **Accepted window:** the bot's worker keeps running after a `COVERED` read, so it can still cancel a stop over a position that just went flat (`_cancel_over_nothing`) before the workers close, leaving a resting ladder with no stop (D5's state); the window is the milliseconds between the read and the app's stop, the same one a crash has, and is not closed here. |
| D5 | **A flat Futures bot is covered only if nothing can open a position:** no position and no ladder order resting is `NOTHING_EXPOSED` and is left; no position but a ladder resting is `UNCOVERED` and is closed. | Accepted | 🤖 Agent decision (the author's reading of "covers the position"; the owner may veto) | The stop is placed only over a position that exists, because a stop over a flat symbol could open one (`EPIC-039L`), so nobody places it while the host is down: a fill of a resting ladder would open a leveraged position with no stop. Closing a flat bot costs nothing (cancel the ladder, no market order), and the bot ends STOPPED, not RECOVERING. |
| D6 | **The deadline is honoured by reading in a share of it and closing in the rest.** The policy spends `READ_SHARE` (half) of `--stop-timeout` reading stops; a bot not read by then is closed unread, and the WARNING says the deadline made closing the safe side. A close that does not finish by the timeout stays in the ledger and the host names it, as for `stop-bots`. The budget gates only the *start* of a read, and one read can outlast the timeout (each REST call is bounded by 30 s), so every bot that may hold a position is put in the ledger as "its stop was not read" before the first read and leaves it when it is left or closed: a host that gives up mid-read names the bots it never reached. The summary line counts accepted closes only. No constant of the unit moves: `STOP_GRACE_SECONDS`, `TimeoutStopSec=62` and `scripts/render_service_files.py` are untouched. | Accepted | 🤖 Agent decision, delegated by the owner | The stop cannot end later than it did; under a slow exchange more bots are closed than strictly needed, never fewer than needed. |
| D7 | **Not changed:** the desktop Stop dialog, the Emergency Stop, `--on-stop stop-bots` (a Futures bot is still refused KEEP there and left, as `headless_runbook.md` §6 says), and the order session (a close never opens one: an automated caller must not undo an Emergency Stop). A RECOVERING Futures bot whose session is closed and whose stop is uncovered therefore stays in the ledger as left, and the WARNING says so. | Accepted | 🤖 Agent decision, delegated by the owner (scope given in the delegation) | Named gaps, in the runbook: §0 and §8. |
| D8 | **A NEUTRAL grid with a resting ladder is not covered by its one stop.** A NEUTRAL grid stands only the stop of the side that covers its position (`NEUTRAL_BOTH_SIDES_VERIFIED` is `False` until check T3), so its resting ladder can fill through zero and open the position of the side no stop covers. It is `UNCOVERED` while any ladder order rests, and is closed. | Accepted | 🤖 Agent decision (review of #626, round 1, finding 3; the owner may veto) | Every running NEUTRAL Futures bot is closed at a host stop until T3 is recorded and both stops stand; LONG and SHORT bots are unaffected. |

## 2a. Constitution check
| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | The choice is in code and tests, not in a runbook sentence: `test_leave_orders_on_a_position_venue.py`, `test_the_run_hosts_default_stop_on_a_futures_bot_on_the_fake_exchange.py`; `TimeoutStopSec` stays guarded by `test_service_files.py`. |
| P2 Verify, don't restate | ✅ | "Covered" is read from the exchange at the moment of the stop, never from the bot's record alone. |
| P3 A copy drifts | ✅ | One judgement (`judge_stop`) serves the halt's words and the host; the close is the existing Stop, not a copy. |
| P4 Green proves only what was tested | ✅ | The fake exchange's own `closePosition` semantics and its open-order lists decide the integration tests; the mutations that flip each branch turn them red (task §5). Not proven: a real exchange. |
| P5 Apply before you invent | ✅ | Reuses `describe_stop`'s reading, `StopBotForHostCommand`, `StopLedger`, the read model, and the stop-and-wait loop of `StopBotsFirst` (now `HostBotStopper`, shared). New: one query, one contract file. |
| P6 Fix the mechanism | ✅ | The O12 answer becomes behaviour of the policy itself, per bot, for every Futures bot, not a runbook caveat. |
| P7 Seam now, variant later | ✅ | `IShutdownPolicy` unchanged; the profile decides; a Coin-M venue is one profile; the read is behind `IExposureProtection`. |
| P8 Ratchets only fall | ✅ | No test or baseline loosened; the god-file and mypy baselines hold. |
| P9 Decide alone | ✅ | D4 to D6 and D8 are decided here and flagged for the owner's veto in the hand-off. |
| P10 Pyramid and units | ✅ | The budget is in seconds and a share (`READ_SHARE`), stated in the docstring and the runbook. |
| P11 Prompt-grade artifacts | ✅ | This record, the task and the docstrings state the contract. |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ⚠️ | Reversible (revert the commit; no stored format changes). It does touch real-money behaviour: a mainnet Futures bot with an uncovered position is now closed at market when the host stops. That is the delegated decision itself, which the owner made; no dependency, setting, unit file, Engine file, user data or secret changes. |

## 3. Alternatives considered
| Alternative | Why it lost |
| :--- | :--- |
| (b) close every Futures position at every stop | Turns each upgrade into a market exit with fees and slippage for positions the exchange already protects. |
| (a) without the fallback: leave every Futures bot | A position whose stop was cancelled by hand, or never placed (a plan with no stop loss), would be left leveraged and unwatched: the O12 answer forbids it. |
| A second reader of the stop in `operations` | Operations cannot read a bot's file or the exchange (module boundary), and the record alone can claim a stop that was cancelled by hand. |
| Ask the executor through its work queue | A worker busy placing orders would delay the read past the deadline; a read racing a placement errs toward closing, which is the safe side. |
| Change `--on-stop stop-bots` too | Outside the delegation; it is the maintenance policy, and its Futures behaviour (refused KEEP) is a named gap in the runbook. |

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Should `--on-stop stop-bots` close a Futures bot (`CLOSE_AT_MARKET`) instead of being refused and leaving it? | Nothing | 2026-10-20 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 to D8 | [EPIC-038M](completed/EPIC-038M_a_futures_bot_at_host_stop.md) | Verified on the fake exchange; GitHub Actions' `-Full` run and the review are on the pull request | The task's §5. |
