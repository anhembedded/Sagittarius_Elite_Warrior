# EPIC-029J1a — Bots on different venues run together: one active bot per venue, not one in the app

**Status:** ✅ Done (2026-10-17)
**Source:** the owner, 2026-10-17, after reading the coordinator's proposal that two bots may run together when they do not share the same venue and symbol: *"còn chuyện multibot thì làm J1a trước đi"* (do J1a first), and *"J2 chưa cần nghĩ tới"* (the second slice, two copies of the app on one account, is not wanted now). The owner has Futures Testnet BTC and ETH bots on the desktop and a Spot mainnet bot on a headless host and wants bots on different venues to run together; the Bots screen said "Start is still blocked: 1 thing left: Bot djwx0w is still active; stop it before starting another".
**Risk:** 🔴 — a real-money rule: the cap that stopped two bots sharing the exchange.
**Complexity:** S — one function and its words; the isolation it relies on was already per venue, and this task proves and records that.
**Epic:** [EPIC-029](../README.md)
**SPEC:** [`SPEC-014`](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None. The task file used to list `EPIC-029H`; the owner heard that it would be dropped for J1a and did not object (told through the coordinating session, 2026-10-17). The owner may veto: restoring it changes only this line.

---

## 1. Context and problem
ADR D20 (`DECISION_2026-10-03_bots_module_and_grid_bot.md`) capped the fast track at one bot holding the exchange, and `other_active_bot` counted every bot of the data root that is not at rest, on any venue (`src/modules/bots/application/services/lifecycle/other_active_bot.py` at `62a815f`). Bots on different venues share no order, account, stream or lease, so the cap there protected nothing and blocked the owner's setup.

## 2. Acceptance criteria
- [x] A bot blocks a Start only when it is on the same venue and not at rest; "active" is unchanged, and a file the store refused still counts as active on every venue. *Unit: `test_other_active_bot_and_budget.py`.*
- [x] The Start path, the readiness reader and the Bots screen answer from that one function. *`test_the_screen_and_start_read_the_same_world_the_same_way.py` (new scenario: a bot active on another venue); `test_bots_run_step.py`.*
- [x] The refusal and the screen's words name the venue: "A bot on Spot Testnet is still active (aaa111); stop it before starting another on Spot Testnet". *`test_bot_readiness_assessment.py`, `test_bot_lifecycle_commands.py`, `test_bots_run_step.py`.* The refusal code is `BotRefusal.ONE_ACTIVE_BOT_PER_VENUE` (was `ONE_RUNNING_BOT_DURING_FAST_TRACK`).
- [x] Two bots on two venues run at once on the fake exchanges, with their orders, fills and PnL attributed by tag and never mixed; a second bot on the same venue is refused; stopping one leaves the other running. *`tests/integration/modules/bots/test_bots_on_two_venues_run_together_on_the_fake_exchange.py`: the composed app (`create_app()`), real Spot and Futures adapters over the one fake server; both bots trade `BTCUSDT`, so the tag alone tells them apart.*
- [x] An Emergency Stop on one venue halts that venue's bots and none on the other. *Already correct before this task (`BotEventRouter.on_switch` routes by `event.venue`; `EmergencyStopCommandHandler` acts on one `VenueTradingScope`); now proved end to end in the same integration file.*
- [x] Nothing is shared between venues by accident, or what is shared is said (section 3a below).
- [x] The headless host with two venues is checked and documented (runbook §8).

## 3. Design
The rule is one function with the venue passed in: `other_active_bot(bot_id, venue, bots, refused_files)`, where `bots` are `(id, venue, state)` rows. Its two callers build the rows from what they hold (the store's readings for Start and the readiness reader, the list's snapshots for the screen); the words come from `readiness_assessment._run_items` with the connection's venue title. The symbol lease stays as it is. No setting, no new port, no state file.

### 3a. What is shared between venues (evidence at `62a815f`)
| Thing | Per venue? | Evidence |
| :--- | :-: | :--- |
| Symbol lease | yes | `TradingSessionState` holds `_symbol_by_owner`; `VenueSessionStates.session_state(venue)` creates one per venue. The integration test starts a Spot and a Futures bot on the same `BTCUSDT` and both hold it. |
| Owner budget and books | yes | `owner_books` is a field of `TradingSessionState` (one per venue); a bot's budget is built from its own parameters (`grid_budgets.py` → `GridBudgetsByProfile`). Caps apply to each bot's budget, not to a sum (J1b). |
| User-data stream | yes | `VenueAssembly.user_data_stream` is built per `VenueAssembly(venue, ...)`; fills reach the bus tagged with the venue and `BotEventRouter._executor_of_tag` drops a fill whose venue is not the executor's. |
| Credentials | yes | `VenueAssembly.credentials_provider`: a mainnet key is `MainnetCredentialsProvider(secret_store, venue)`, a testnet key `EnvFirstCredentialsProvider(source, venue)` with a pair of variables per venue; `order_credentials` wraps it in the venue's own key gate. |
| Session switch (Emergency Stop) | yes | `TradingSwitchChangedEvent.venue` is required; `BotExecutors.on_venue(venue)`. |
| Request-weight gate | **there is none** | No limiter or weight counter exists in `src/`. Weight is managed by read intervals and by each bot's own rate-limit pause (`grid_rate_limit_pause.py`); the exchange counts it per IP per API family (venues on different hosts do not share a counter). With one active bot per venue nothing needs adding up; with several on one venue (J1b) it does. Whether a 418 IP ban on one API family also stops another family's requests is **not verified** (no offline source), and the fake exchange cannot answer it. |
| Order pacer | per bot | `MonotonicOrderPacer` is built per executor. One bot per venue makes it per venue; J1b must pace per venue. |

Nothing in the application is shared across venues by accident, so no owner decision was needed. The two gaps (request weight, pacer) are J1b's, recorded in its file.

### 3b. The headless host with bots on two venues (`run --start-planned`, `--resume-recovering`, `--resume-halted`)
Checked in `host_steps.py` and the two `*_for_host` handlers; no host change, because each behaviour is the written decision O8 and none is wrong for one venue:
- `--start-planned` asks the same Start, so a planned testnet bot and a planned mainnet bot start together when the mainnet venue is confirmed; two planned bots on one venue start one (the lowest bot id, the run is sorted) and the other is logged `was not started: ONE_ACTIVE_BOT_PER_VENUE (...)`. The integration file proves it with the real `StartPlannedBots`.
- `--confirm-venue` names one venue per run. `mainnet_start_refusal` and `mainnet_resume_refusal` judge **every** wanted real-money bot before anything boots, so real-money bots on **two mainnet venues** make `--start-planned` and `--resume-recovering` exit `2`, naming `--confirm-venue <first venue>` and "one mainnet venue per run": no single run can start or resume both. `--resume-halted` skips and names the unconfirmed venue instead of refusing. This is documented in the runbook; whether a run may confirm more than one venue is the owner's call (a real-money choice), not taken here.
- A venue's bots do not wait for another venue's: the cap is judged per venue.

## 3c. Reuse
None: no UI or application need. The change moves one existing function's contract; the test world reuses `readiness_world`, `booted_futures_bots`' composition (`grid_executor_deps`) and the fake server.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/lifecycle/other_active_bot.py` | the rule is per venue |
| `.../readiness/bot_readiness_reader.py`, `src/modules/bots/ui/bots_screen/selected_bot.py` | pass the venue and the rows' venues |
| `.../readiness/readiness_assessment.py`, `src/modules/bots/contracts/bot_command_result.py` | the words name the venue; refusal `ONE_ACTIVE_BOT_PER_VENUE` |
| `tests/unit/modules/bots/...`, `tests/integration/modules/bots/two_venues_bots_world.py`, `test_bots_on_two_venues_run_together_on_the_fake_exchange.py`, `conftest.py` | the proofs above |
| `Docs/...` | section 6 |

## 5. Testing
`tests/unit/modules/bots` (3 990 tests green), the new integration file (6 tests), the architecture guards. Mutation: replacing `other_venue is venue` with `True` turns the new unit tests and the first integration test red; restored. The behaviour tests that a bot on another venue does not block were written after the signature change, so their red was the old signature and the old words, then the mutation above is what shows they can fail for the right reason. The gate evidence is the pull request's `ci-local.ps1 -Full` job log.

## 6. Docs touched
`Docs/SPEC/SPEC-014_run_a_grid_bot.md` §5 (the Run item and the click race), `Docs/OPERATIONS/headless_runbook.md` §8, `Docs/MODULES/bots/06-runtime.md` ("Built: Start"), `Docs/VOCABULARY/README.md` (`bots`: **Venue slot**), the ADR's D20 note, this epic's README and TRACKING.

## Implementation notes (written when done)
- The Emergency Stop needed no fix: the integration file shows it halts the Futures bot (`SWITCH_OFF`, ladder gone, session disabled) while the Spot bot stays `RUNNING` with its ladder resting.
- The new two-venue test world needed one harness fix: a bot's order turn delivers the exchange's reports while a delivery is handing it a fill, and two venues make that nest `asyncio.run`; the inner call now leaves the rest to the outer one. This is the test world only.
- A refused file still counts as active on every venue (its venue is unknown): kept, and tested.
- Not done, by decision: J1b (several bots on one venue) and J2 (two copies of the app) — split into their own files.
