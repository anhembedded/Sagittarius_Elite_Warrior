# Systems analysis of AI-driven development — 2026-10-09

The repository copy of the owner's page (https://claude.ai/artifact/SSMXy58rtcwCYrXn1kraCJ). It records the data, the model and the sources this epic rests on. Measured on `master-warrior` at `880699a`.

## 1. Finding
Knowledge of what the repository already has does not reach the AI when it decides what to write (Meadows' leverage point 6, information flows). The project has invested mostly in rules and review rounds (points 5 and 12), where returns are diminishing.

## 2. Data
**Weekly share of `fix:` commits** (`git log --no-merges origin/master-warrior`, 1,932 commits from 2026-08-02):

| Week | W32 | W33 | W34 | W35 | W36 | W37 | W38 | W39 | W40 | W41* |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| commits | 98 | 198 | 201 | 250 | 96 | 81 | 279 | 139 | 298 | 290 |
| `fix:` | 18 | 32 | 39 | 38 | 34 | 21 | 24 | 38 | 94 | 81 |
| share | 18% | 16% | 19% | 15% | 35% | 26% | 9% | 27% | 32% | 28% |

*W41 = 5–9 October only. Weeks 32–35: 17.0%; weeks 39–41: 29.3%; from week 39, 213 fix commits against 173 feature commits.

**Root-cause classes of 192 bug reports** (one agent read each file's title and cause and assigned one primary class; about 12 low-confidence):

| Class | Count | Found by the owner |
| :-- | --: | --: |
| E UI state and layout | 35 | 27 |
| C concurrency, ordering, lifecycle | 31 | 15 |
| H-test test, CI, script infrastructure | 26 | 0 |
| B forgiving test double, blind gate | 23 | 4 |
| D exchange or API semantics | 21 | 12 |
| A did not reuse; diverging siblings | 18 | 9 |
| H other | 18 | 7 |
| G missing requirement | 16 | 10 |
| F persistence and restore | 4 | 2 |

A + B: 41 (21.4%); 11 of the first 103 reports, 30 of the next 89. Owner-found: 86 of 192 (52% of the 166 product bugs). Examples — A: BUG-155, 133, 191, 194, 165, 113; B: BUG-144, 126/127, 022, 115.

**Size:** `src/` 143,585 lines in 1,452 files; `tests/` 180,262 lines in 1,004 files; 59 architecture guards; 20 rule files (672 lines) + 164 lines of CLAUDE.md and ONBOARDING; 8 case studies.

**One day (2026-10-09), six incidents of one shape:** BUG-194 (Start skipped the history read Stop and Resume do); BUG-197 (no shared log-level restore); two sessions took BOT-173; a false "Blocks Start" already handled by an open PR; a reviewer spawned on a guessed branch name; an `inventory_mismatch` warning with no "agreed" log on the second check.

## 3. Model
- **R1, the fix loop:** bugs → fix sessions and new rules → more code and rules in context → less knowledge of what exists reaches the AI → less reuse → more copies → more bugs.
- **R2, the duplication loop:** copies → a larger repository → the original mechanism is harder to find → more copies.
- **B1, gate and review:** bugs → more rules and review → fewer bugs, after a delay; its side effect (rules in context) feeds R1.
- **Archetypes:** *fixes that fail* (rules added for bugs dilute context and cause more bugs); *shifting the burden* (the owner and reviewers absorb defects, so the fundamental fix is never built).

## 4. Interventions
037A catalog (point 6) · 037C "only one" guards and 037D sibling parity (point 8) · 037E demanding fake exchange (point 9) · 037B goals and metrics (points 3 and 4) · 037F one id issuer (coordination).

## 5. Limits
The `fix:` prefix is a proxy; the classification has a single rater; the rise coincides with the start of real-money trading (correlation, not proven cause); the GitClear and DORA figures come from secondary coverage.

## 6. Sources
- Donella Meadows, [Leverage Points: Places to Intervene in a System](https://donellameadows.org/archives/leverage-points-places-to-intervene-in-a-system/).
- LeadDev, [How AI-generated code accelerates technical debt](https://leaddev.com/software-quality/how-ai-generated-code-accelerates-technical-debt) (GitClear 2025: duplicated 5+-line blocks up eightfold in 2024; copy/paste exceeded moved lines).
- InfoQ, [2024 DORA Report](https://www.infoq.com/news/2024/11/2024-dora-report/) (with AI adoption, throughput −1.5%, stability −7.2%).
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 2025-09-29.
- Peter Senge, *The Fifth Discipline* (1990); Donella Meadows, *Thinking in Systems* (2008); John Sterman, *Business Dynamics* (2000).
