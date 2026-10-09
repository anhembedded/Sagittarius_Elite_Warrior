# EPIC-037 — The AI finds what already exists before it writes, and the machine stops it when it does not

- **Status:** 🔵 Planned — scaffolded 2026-10-09; **not started** (the owner: "lưu vào 1 epic, để tuần sau làm tiếp việc này", save it in an epic and continue next week)
- **Repositories:** Elite. No Engine change is expected.
- **Origin:** the owner's systems-thinking review of 2026-10-09: *"there are module features that could use a mechanism that already exists, but when the AI develops it does not notice, e.g. choosing the bot's symbol: another screen already had a picker mechanism, but the bot built a different one instead of reusing it"* (translated). The analysis, its data and its sources are recorded in [`ANALYSIS_2026-10-09_systems_thinking.md`](ANALYSIS_2026-10-09_systems_thinking.md).
- **North star:** [`ANALYSIS_2026-10-09_systems_thinking.md`](ANALYSIS_2026-10-09_systems_thinking.md). The owner's page (https://claude.ai/artifact/SSMXy58rtcwCYrXn1kraCJ, private, English, with a systems-thinking primer) is a secondary reference only.
- **Tracking:** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** None to start. `EPIC-037E` adds a test dependency (`hypothesis`) that needs the owner's approval (`commit-rule.md` §3).

---

## 1. Decisions already made
1. The owner accepted the analysis as the plan to continue next week (2026-10-09). The four interventions, their order and the four-week targets come from it; nothing here is started.
2. Interventions act on leverage points, not on more rules: information flow first (`037A`), then balancing loops (`037C`, `037D`), then delays (`037E`), with goals and metrics (`037B`) measured from day one.
3. No new rule is added to the always-loaded tree by this epic: the catalog loads by path (`paths:` front matter), so it reaches a session only when it touches matching files.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-09) | When the epic is done |
| :--- | :-: | :-: |
| Weekly share of `fix:` commits (non-merge) | 29.3% (weeks 39–41) | under 20% for two consecutive weeks |
| Share of new bug reports in class A (did not reuse) + B (forgiving double) | 33.7% (BUG-106 onward) | under 15% of reports filed after Phase 1 |
| Share of product bugs found by the owner in real use | ~52% (86/166) | falling, reported by the audit |
| Duplicated canonical mechanisms reaching master | not measured | 0, enforced by guard |
| Lines of rules and guidance for the AI (CLAUDE.md, ONBOARDING, `.claude/rules`) | 836 | not rising |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-037A](incomplete/EPIC-037A_capability_catalog.md) | A capability catalog the AI receives when it touches UI or application code | Elite | None | 🟢 | Planned |
| [EPIC-037B](incomplete/EPIC-037B_system_health_metrics.md) | Bugs carry a root-cause class and the audit reports system-health metrics | Elite | None | 🟢 | Planned |
| [EPIC-037F](incomplete/EPIC-037F_one_place_issues_task_ids.md) | One place issues BOT and BUG ids, open PR branches included | Elite | None | 🟢 | Planned |
| [EPIC-037C](incomplete/EPIC-037C_only_one_guards.md) | "Only one" guards: a second copy of a canonical mechanism turns CI red | Elite | 037A | 🟡 | Planned |
| [EPIC-037D](incomplete/EPIC-037D_sibling_parity_tests.md) | Sibling paths that do one job prove they give one result | Elite | None | 🟡 | Planned |
| [EPIC-037E](incomplete/EPIC-037E_demanding_fake_exchange.md) | The fake exchange is demanding by default: faults, reorderings and invariants | Elite | 037D | 🔴 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 0 — Information and measurement (037A, 037B, 037F) | The catalog covers every package under `src/support/`; the baseline metrics are recorded | Completeness guard green; the first audit report with the new metrics. Not run |
| 1 — Feedback (037C, 037D) | Five canonical mechanisms guarded; three sibling families under parity tests | Each guard and parity test shown red by re-introducing an old bug (BUG-155, BUG-191, BUG-194). Not run |
| 2 — Demanding fake (037E) | Integration tests of bots and trading run with faults on by default | BUG-194 and BUG-195's shape reproduced from a seed alone. Not run |
| 3 — Review | Metrics compared with the 2026-10-09 baseline; keep, adjust or drop each intervention | The owner's decision recorded in Notes. Not run |

## 5. Out of scope
- Adding rules to the always-loaded tree, or more review rounds (leverage points 5 and 12; the analysis shows diminishing returns).
- Running anything against a real exchange; every fault is injected on the fake.
- PRO-007's PnL and risk figures (a separate proposal).

## Notes (newest first)
- **2026-10-09** — Scaffolded from the systems analysis; documentation only, not started.
