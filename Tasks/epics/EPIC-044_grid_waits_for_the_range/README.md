# EPIC-044 — A Grid started away from its range waits for the price, then lays its ladder

- **Status:** 🟡 Phase 3 in progress (the state and the entry are merged, #682; the surfaces are in review)
- **Repositories:** Elite
- **Origin:** the owner, 2026-10-21, through the coordinating session: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"*, then *"không thời hạn chờ"*, then *"OK"* to always waiting with the logic mirrored for Short. Translated: if the price is out of the range the bot still starts, but only begins laying orders when the price is inside the range; no time limit; always wait, mirrored for Short.
- **North star:** [`Docs/SPEC/SPEC-014_run_a_grid_bot.md`](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (Start with the price outside the range) and [`Docs/MODULES/bots/state-machines.md`](../../../Docs/MODULES/bots/state-machines.md); both change with the code slices.
- **Decisions:** [`DECISION_2026-10-21_a_grid_waits_for_the_range.md`](DECISION_2026-10-21_a_grid_waits_for_the_range.md) — the rule (owner), the state, the entry rule, the checks, the surfaces, the backtest.
- **Dependencies:** [`EPIC-042`](../EPIC-042_halt_auto_recovery/README.md) (the precedent for a state a machine owns), `BOT-209`/`EPIC-043`/`BOT-218` (the Plan banner, the state badge, `PlanColumn`) for slice C; the UI work in flight (`BOT-219` #677, `BUG-245` #678) and alerting (`EPIC-036D9` #674) for slice C's files.

---

## 1. Decisions already made
1. The rule, for every direction, Spot and Futures, mainnet and testnet: start outside the range, place nothing, hold nothing, wait without a time limit, lay the ladder when the price is inside, exactly as a normal start would. No "start now". Stop works at once; stop loss and take profit do nothing while waiting (ADR D1, the owner's).
2. The rest, D2–D12, was reviewed in three rounds on PR #679 (round 1: eight Should-fix points, all answered: `may_hold_exposure`, the entry decided in `AWAITING_RANGE` on a fresh book read, the failure split before `range_entered`, a flat Resume waits, `switch_off` halts, the replay walk, the list of state sets and a guard over them) and accepted on 2026-10-21; D8 (`switch_off` halts) is the coordinator's default for the owner, who may veto it. The owner answered O1–O3 as recommended (restart through `RECOVERING`; a refusal of the plan at entry halts; the backtest benchmark starts at the entry step). D9 depends on a separate bug: a Futures `bot resume` after a host restart is refused "unexpected open positions".

## 2. Goals — measurable
| Metric | Today (measured 2026-10-21, `849d973`) | When the epic is done |
| :--- | :-: | :-: |
| A SHORT started above its range | market-shorts ≈ 10 950 USDT (0.1542 BTC) before one order, and the check says "places BUY orders only" | places nothing; waits; shorts only once the price is inside the range |
| A LONG started below its range | refused (`PRICE_BELOW_RANGE`) | starts and waits |
| A LONG started above its range / a SHORT below | lays 11 BUYs / 11 SELLs | starts and waits |
| A restart while waiting | not possible (the state does not exist) | `RECOVERING`, reconciles, returns to waiting; nothing laid |
| Live and backtest entry bar | no waiting in either | the same bar (a test) |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-044A](completed/EPIC-044A_the_decision_record.md) | The decision record and this epic's scaffold (docs PR) | Elite | None | 🟢 | Done (2026-10-21) |
| [EPIC-044B](incomplete/EPIC-044B_the_state_and_the_entry.md) | `AWAITING_RANGE`: the state, the entry, the informational checks, the restart row, with the red-before tests | Elite | 044A accepted | 🔴 | Merged (#682); the Futures restart test on the VPS is open |
| [EPIC-044C](incomplete/EPIC-044C_the_waiting_bot_is_shown_and_told.md) | The badge, the Plan banner line, the table, `bot list`/`bot show`, the heartbeat and daily summary, the entry alert, with frames | Elite | 044B; `#677`, `#678`, `#674` merged | 🟡 | In review |
| [EPIC-044D](incomplete/EPIC-044D_the_backtest_waits_the_same_way.md) | The Grid's replay waits and enters by the same rule; live and backtest agree on the entry bar | Elite | 044B | 🟡 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 — decision | The ADR is read by the reviewer and accepted by the coordinator; O1–O3 are answered (done 2026-10-21; PASS in round 3) | The reviewer's PR comment; the coordinator's acceptance. Not run |
| 2 — domain and lifecycle | For each of LONG, SHORT, NEUTRAL × below/above: start waits with zero orders, entry lays the expected ladder at the entry price; a restart while waiting stays waiting; Stop while waiting cancels nothing; SL/TP do nothing; a refusal at entry; mainnet and testnet alike | The tests of 044B red on `849d973`, green after; both gate logs |
| 3 — surfaces | Every surface that shows a bot says it is waiting; one alert on entry | Frames in the CI artifact; the unit and integration tests of 044C |
| 4 — backtest | The replay waits; the entry bar equals the live one | The parity test |

## 5. Out of scope
- Resuming a HALTED or AWAITING_RECOVERY bot while the price is outside the range: it holds inventory or a position and keeps `resume_plan` (ADR §2.2).
- Resuming a flat HALTED SHORT/NEUTRAL bot (`GridResumeSequence.propose` sizes a LONG only): existing, unchanged.
- A host step that re-arms waiting bots without `--resume-recovering` (ADR O1).
- A dwell, a hysteresis or a wait limit on entry (ADR §3).
- Any config key, setting, dependency or Engine file.

## Notes (newest first)
- **2026-10-21** — Epic scaffolded with the decision record; a probe on `849d973` found a SHORT above its range plans a 0.1542 BTC market short before any order while the check says it "places BUY orders only".
