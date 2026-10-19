# ADR — A venue's order session opened for one bot resumes no other bot

**Epic:** [EPIC-029](README.md)
**Date:** 2026-10-19
**Status:** Accepted
**Decided by:** 🤖 Agent decision delegated by the owner, relayed by the coordinator session (ONBOARDING §7: an owner decision that carries a recommendation, passes every invariant, is reversible and adds no real-money action). The owner delegated the batch ("cho subsession làm hết cho tui đi") and earlier asked for decisions "dựa trên hiến pháp"; the owner may veto, which reverses it by a later task.

| Label | Meaning |
| :--- | :--- |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7 |

## 1. Context
`BOT-183` (filed with `EPIC-029J1b`). Opening a venue's order session publishes `TradingSwitchChangedEvent(enabled=True)` for the venue, and `BotEventRouter.on_switch` → `GridFacts._apply_switch` ran the reconcile of every `RECOVERING` bot of that venue. `EPIC-029J1b` closed the Start path (a Start is refused while a bot of the venue is `RECOVERING`). A Resume of a halted bot, `run --resume-halted` and the operator's `bot stop` still opened the same session and put each `RECOVERING` bot beside it back to work (a RUNNING bot laid its ladder). ADR 038 O2 says a host never resumes a bot by itself.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | A Resume, `--resume-halted` or an operator stop of bot X does not put a `RECOVERING` bot Y of the same venue back to work; Y waits for its own Resume or for `--resume-recovering`. | Accepted | 🤖 Agent decision (owner delegated) | The opening is announced as opened *for* X (`TradingSwitchChangedEvent.opened_for`); Y acts only on its own opening or on an opening for no bot. The operator who stops X on a mainnet venue is told Y keeps waiting. |
| D2 | An opener that is no bot's (a manual order, a strategy) and the host's `--resume-recovering` name no bot (`None`) and still wake every `RECOVERING` bot of the venue. | Accepted | 🤖 Agent decision | `--resume-recovering` keeps its purpose. A manual order or a strategy opening the session still wakes them: a limit this decision leaves, listed in §4. |

## 2a. Constitution check
| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | The rule is a field the event carries and a branch in `GridFacts._apply_switch`, held by `test_a_recovering_bot_acts_only_on_a_session_opened_for_it.py` and the composed-app test in `test_several_bots_on_one_venue_run_together_on_the_fake_exchange.py`, red under mutation. |
| P2 Verify, don't restate | ✅ | Every claim above was read in the code at `159fbfd` (`session_readiness.py`, `bot_event_router.py`, `grid_facts.py`). |
| P3 A copy drifts | ✅ | One field on one event; no second list of who may wake whom. The CLI help and runbook sentences that stated the old behaviour are corrected in the same change. |
| P4 Green proves only what was tested | ✅ | The composed-app test starts from a real restart (`open_sessions=False`) on the fake exchange. |
| P5 Apply before you invent | ✅ | Carries the opener on the existing event, as `cause` already is; no new bus type. |
| P6 Fix the mechanism | ✅ | The event gains the fact it lacked, rather than every opener filtering its own bots. |
| P7 Seam now, variant later | ✅ | `opened_for` defaults to `None` (today's behaviour) so a non-bot opener needs no change; a "wake only bots the owner named" variant is a later task. |
| P8 Ratchets only fall | ✅ | No test, baseline or threshold loosened; one test's expected sentence changes with the behaviour it asserted (`test_the_mainnet_refusal_names_the_other_recovering_bots_that_keep_waiting`). |
| P9 Decide alone | ✅ | Delegated by the owner; recorded here. |
| P10 Pyramid and units | ✅ | Unit tests for the event, the router, the facts and each opener; one integration journey. |
| P11 Prompt-grade artifacts | ✅ | The port, the event and the opener helpers document the new parameter. |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | Revert the branch in `_apply_switch` (or pass `None`). It adds no order, cancel or close; it only withholds a reconcile the owner did not ask for. No dependency, setting or Engine file changes. |

## 3. Alternatives considered
- **Leave it and document it** (the runbook's "resume the recovering bots deliberately first"): rejected, a real-money bot would trade without the owner's command and the guard was a sentence.
- **Refuse the opener while any bot of the venue is `RECOVERING`**, as Start does: rejected for a Resume, a halted bot's Resume and an operator stop are how the owner gets out of the situation.
- **Filter in each opener** (skip the event's bots in `BotRunner`): rejected, the router receives the event from every opener, so the fact belongs on the event (P6).

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | A manual order or a strategy arm that opens a closed session (`opened_for=None`) still reconciles every `RECOVERING` bot of the venue. Should those openers also leave them waiting? | Nothing in this change | 2026-10-19 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1, D2 | [BOT-183](../../completed/BOT-183_a_session_opened_for_one_bot_does_not_resume_the_recovering_bots_beside_it.md) | Verified | Tests above, red under mutation (`_apply_switch` reconciling regardless). |
