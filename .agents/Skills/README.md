# `.agents/Skills/` — unattended runs

| Prompt | Runs | Produces |
| :--- | :--- | :--- |
| `.claude/skills/test-health/SKILL.md` | Routine, every 3 days | `Tasks/reports/test_health/<date>.md` — the delta against the baseline, one line when nothing changed |
| `process-drift.prompt.md` | Routine, every 3 days | `Tasks/reports/process_drift/<date>.md` — rule contradictions, stale claims, board orphans, reference rot |
| `epic-025.prompt.md` | on demand, when the user hands it a step | one verified step of the module split |

The seven persona agents (Bolt, Doctor, Janitor, Palette, Scout, Scribe, Sentinel) were retired on 2026-09-17: twenty days of two-daily runs produced no pull request and no journal entry, and their concerns are covered by the gate (`ruff` `S`/`ERA`, `mypy`) or by `EPIC-025`'s own measurements. Their prompts live in git history.

## Rules every unattended run obeys
1. **Verify, don't restate.** A fact that can change is written as the command that answers it; no counts, versions or dates as current state; a rule is linked, never copied; a path is checked in this run before it is cited. `scripts/check_skill_prompt_references.py` fails on a cited path that does not exist and runs in the gate. `[gate]`
2. **Read first:** `CLAUDE.md`, `ONBOARDING.md` (§7 authority, §8 traps, §12.5 principles), then the rules the change touches (`ls .agents/rules/`).
3. **The gate:** `ci-rule.md` §1 — every commit runs the static checks and the architecture guards; a pull request runs `-Full` on its final tree, log file grepped. A missing tool is installed (`install-rule.md` §3), never a reason to skip.
4. **Output is durable even when empty.** Every audit run writes its dated report file, commits it and merges it — a report under `Tasks/reports/` is documentation-only and `ONBOARDING.md` §7 lets it merge. An empty run reads *"no change since <date>"* and is a correct outcome; a run that could not build its environment says so in the same file. Silence is never success.
5. **A finding is not fixed by the audit.** Report it with `file:line`, the rule it breaks and what breaks if left; a fix is a separate change through the normal path (§7). The one exception is a finding the run itself created.
6. **Never:** weaken, skip or delete a test; change `requirements.txt`, `pyproject.toml`, ruff/mypy configuration or a Routine; touch the engine repository; commit secrets, `.db`, `logs/`, `state/`, a virtualenv, or `.obsidian/`.
7. **Commits** follow `commit-rule.md`; the trailer names the assistant that ran.
