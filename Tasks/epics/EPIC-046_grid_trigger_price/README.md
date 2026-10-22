# EPIC-046 — A Grid with a trigger price activates like a limit order: only at that price or better

- **Status:** 🟡 Phase 1 in progress (046A: the rule and the live entry, pull request open)
- **Repositories:** Elite
- **Origin:** the owner, 2026-10-22, through the coordinating session: *"cái phần giá kích hoạt làm chưa ta? tui muốn kích hoạt giống limit, giá tốt hơn giá đó mới kích hoạt grid"*. Translated: "Has the trigger price been built? I want it to activate like a limit order: the grid activates only when the price is better than that price."
- **North star:** [`Docs/SPEC/SPEC-014_run_a_grid_bot.md`](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (the Start checks) and [`Docs/MODULES/bots/state-machines.md`](../../../Docs/MODULES/bots/state-machines.md) (`AWAITING_RANGE`); both change with the slices.
- **Decisions:** [`DECISION_2026-10-22_a_grid_trigger_price.md`](DECISION_2026-10-22_a_grid_trigger_price.md) — the rule (owner), what "better" means, the price source and the state, the latch, the validation, the surfaces.
- **Dependencies:** [`EPIC-044`](../EPIC-044_grid_waits_for_the_range/README.md) (the wait this extends).

---

## 1. Decisions already made
1. The rule is the owner's: an optional trigger price; the grid activates only at a better price, like a limit order (ADR D0).
2. D1–D6 are the author's proposed defaults, for the reviewer's read, the coordinator's acceptance and the owner's veto: LONG ≤ trigger, SHORT ≥ trigger, NEUTRAL refused (O1 asked); the same `AWAITING_RANGE` wait and price source, the range judged first; the lifecycle is the latch; a trigger outside the range is refused at Design.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-22, `f850b18`) | When the epic is done |
| :--- | :-: | :-: |
| A LONG with trigger 125, started at 135 in the range 100–140 | no trigger exists; lays its ladder at 135 | places nothing; lays at the first price ≤ 125 |
| A SHORT with trigger 125, started at 115 | no trigger exists | places nothing; lays at the first price ≥ 125 |
| The price returns across the trigger after the ladder is laid | — | the bot keeps running |
| A backtest of a triggered plan | — | enters at the same step as the live rule (a test) |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-046A](completed/EPIC-046A_the_trigger_gates_the_entry.md) | The decision record, `trigger_price` on `GridParams`, one entry gate for the start, the wait, the confirmation and the flat Resume, the Start check's words and the entry price | Elite | None | 🔴 | Done (2026-10-22), pull request open |
| [EPIC-046B](incomplete/EPIC-046B_the_trigger_is_shown_and_backtested.md) | The Plan editor field, the waiting words on the banner, `bot list` and `bot show`, the Discord entry alert, and the backtest entering by the same gate | Elite | 046A merged | 🟡 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 — rule and live entry | LONG and SHORT, Spot and Futures: short of the trigger places nothing; at or better lays what a normal start there would; the latch holds through a price reversal and a restart; a flat Resume asks the trigger; validation refuses in words | 046A's tests; both gate logs on the PR |
| 2 — surfaces and backtest | Every place that shows a waiting bot names the trigger; the replay enters at the live step | 046B's tests and frames; the parity test |

## 5. Out of scope
- A NEUTRAL trigger (ADR O1).
- Renaming `AWAITING_RANGE` (ADR §3).
- A dwell, a hysteresis or a time limit on the trigger.
- Any config key, setting, dependency or Engine file.

## Notes (newest first)
- **2026-10-22** — Epic scaffolded with the decision record and 046A; split in two pull requests (the rule and the live entry first, the surfaces and the backtest next), told to the coordinating session before building.
